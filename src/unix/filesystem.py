"""
Virtual filesystem for the in-game Unix machine.

The default tree (files, permissions, owners) is data: ``src/data/filesystem.json``.
Player changes are stored as an overlay (created / modified / deleted files,
permissions, owners) so saves stay small and directories can be reset.

Public file operations accept either a bare name in the current directory or
a path (relative, absolute, ``~``-prefixed); paths are handled by temporarily
changing into the parent directory.
"""

from __future__ import annotations

import copy
import functools
import json
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

HOME_PATH = ["home", "pilot", "blthll"]
DEFAULT_FS_FILE = Path(__file__).resolve().parent.parent / "data" / "filesystem.json"


@functools.lru_cache(maxsize=1)
def _load_default_tree() -> dict:
    with open(DEFAULT_FS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _collect_owners(node: dict, path: str, owners: dict) -> None:
    for name, child in node.get("dirs", {}).items():
        child_path = f"{path}/{name}"
        if "owner" in child:
            owners[child_path] = child["owner"]
        _collect_owners(child, child_path, owners)
    for name, entry in node.get("files", {}).items():
        if isinstance(entry, dict) and "owner" in entry:
            owners[f"{path}/{name}"] = entry["owner"]


_SYMBOLIC_MODE = re.compile(r"^([ugoa]*)([+\-=])([rwx]*)$")


def apply_symbolic_mode(current: str, mode: str) -> str | None:
    """Apply chmod-style symbolic clauses (``+x``, ``u+x``, ``go-w``, ``a=r,u+w``).

    ``current`` is a 9-char permission string. Returns the new string, or None
    if ``mode`` isn't a valid symbolic mode.
    """
    perms = list(current if len(current) == 9 else (current * 3)[:9])
    for clause in mode.split(","):
        m = _SYMBOLIC_MODE.match(clause)
        if not m:
            return None
        who, op, what = m.groups()
        who = who.replace("a", "ugo") or "ugo"
        for w in set(who):
            base = {"u": 0, "g": 3, "o": 6}[w]
            for i, bit in enumerate("rwx"):
                idx = base + i
                if op == "=":
                    perms[idx] = bit if bit in what else "-"
                elif bit in what:
                    perms[idx] = bit if op == "+" else "-"
    return "".join(perms)


def _path_aware(method):
    """Let a cwd-relative method accept a path as its first argument."""

    @functools.wraps(method)
    def wrapper(self, name, *args, **kwargs):
        if isinstance(name, str) and ("/" in name.rstrip("/") or name.startswith("~")):
            with self._in_parent(name) as base:
                if base is None:
                    return self._missing_parent_result(method.__name__, name)
                return method(self, base, *args, **kwargs)
        return method(self, name, *args, **kwargs)

    return wrapper


class VirtualFileSystem:
    """A virtual filesystem with directories and files"""

    # Maximum total size for user-created files (16KB)
    MAX_USER_FILES_SIZE = 16 * 1024

    def __init__(self, saved_state=None):
        """
        Initialize the filesystem structure

        Args:
            saved_state: Optional saved filesystem state to restore
        """
        # Current directory path as a list (e.g., ['home', 'pilot', 'blthll'])
        self.current_path = ['home', 'pilot', 'blthll']

        # Load default filesystem
        self.filesystem = self._get_default_filesystem()

        # Track user modifications separately
        self.user_created_files = {}  # path -> content
        self.user_created_dirs = []   # list of paths
        self.user_modified_files = {}  # path -> content
        self.user_deleted_files = set()  # paths of default files that have been deleted/moved

        # File permissions: path -> permission string
        # Can be 3 characters (user only: "rwx") or 9 characters (user, group, other: "rwxrwxrwx")
        # Default: "rwx" for all files (user rwx)
        # Permissions can be overridden in the filesystem structure or via chmod
        self.file_permissions = {}  # path -> permission string like "rwx" or "rwxrwxrwx"

        # File ownership system
        self.current_user = "pilot"  # Current user (can be "pilot" or "root")
        self.default_file_owners = self._get_default_file_owners()
        # Track ownership for moved/modified files (path -> owner)
        self.file_owners = {}  # path -> owner username

        # File timestamps: path -> {'access': datetime, 'modify': datetime, 'change': datetime}
        # All timestamps are stored as ISO format strings for JSON serialization
        self.file_timestamps = {}  # path -> {'access': str, 'modify': str, 'change': str}

        # Initialize default timestamps for existing files
        self._initialize_default_timestamps()

        # Restore saved state if provided
        if saved_state:
            self._restore_state(saved_state)

    def _extract_file_content(self, file_entry):
        """
        Extract content from a file entry in the filesystem structure.
        Supports both old format (list) and new format (dict with 'content').

        Args:
            file_entry: Either a list of strings or a dict with 'content' key

        Returns:
            list: File content as list of strings
        """
        if isinstance(file_entry, list):
            return file_entry
        elif isinstance(file_entry, dict) and 'content' in file_entry:
            content = file_entry['content']
            if isinstance(content, list):
                return content
            else:
                return [content]
        else:
            # Fallback for string content
            return [file_entry]

    def _extract_file_permissions(self, file_entry, filename, full_path):
        """
        Extract permissions from a file entry in the filesystem structure.
        Supports both old format (list, defaults to 'rwxrwxrwx') and new format (dict with 'permissions').
        Permissions can be 3-char (user only) or 9-char (user, group, other) format.

        Args:
            file_entry: Either a list of strings or a dict with 'content' and optionally 'permissions'
            filename: Name of the file (for extension-based fallback, though we now default to rwxrwxrwx)
            full_path: Full path to the file

        Returns:
            str: Permission string like "rwx" (3 chars) or "rwxrwxrwx" (9 chars)
        """
        # New format: dict with permissions
        if isinstance(file_entry, dict) and 'permissions' in file_entry:
            perms = file_entry['permissions']
            # If 3-char format, expand to 9-char by repeating for group and other
            if len(perms) == 3:
                return perms + perms + perms  # user, group, other all same
            return perms

        # Old format (list) or new format without permissions: default to 'rwxrwxrwx'
        return "rwxrwxrwx"

    def _get_default_file_owners(self):
        """Owners declared in filesystem.json. Unlisted paths belong to the current user."""
        owners: dict[str, str] = {}
        _collect_owners(_load_default_tree(), "", owners)
        return owners

    def _initialize_default_timestamps(self):
        """Initialize default timestamps for all existing files in the filesystem"""
        # Default timestamp (game start time)
        default_time = datetime.now().isoformat()

        def _walk_filesystem(node, current_path=""):
            """Recursively walk filesystem to find all files"""
            if 'files' in node:
                for filename in node['files']:
                    full_path = f"{current_path}/{filename}" if current_path else f"/{filename}"
                    if full_path not in self.file_timestamps:
                        self.file_timestamps[full_path] = {
                            'access': default_time,
                            'modify': default_time,
                            'change': default_time
                        }
            if 'dirs' in node:
                for dirname, dirnode in node['dirs'].items():
                    new_path = f"{current_path}/{dirname}" if current_path else f"/{dirname}"
                    _walk_filesystem(dirnode, new_path)

        _walk_filesystem(self.filesystem, "")

    def _get_timestamp(self, full_path, timestamp_type='access'):
        """
        Get a timestamp for a file

        Args:
            full_path: Full path to the file
            timestamp_type: 'access', 'modify', or 'change'

        Returns:
            str: ISO format timestamp string
        """
        if full_path not in self.file_timestamps:
            # Initialize with current time
            now = datetime.now().isoformat()
            self.file_timestamps[full_path] = {
                'access': now,
                'modify': now,
                'change': now
            }
        return self.file_timestamps[full_path].get(timestamp_type, datetime.now().isoformat())

    def _update_timestamp(self, full_path, timestamp_type='access'):
        """
        Update a timestamp for a file

        Args:
            full_path: Full path to the file
            timestamp_type: 'access', 'modify', or 'change'
        """
        now = datetime.now().isoformat()
        if full_path not in self.file_timestamps:
            self.file_timestamps[full_path] = {
                'access': now,
                'modify': now,
                'change': now
            }
        self.file_timestamps[full_path][timestamp_type] = now

    def _get_default_filesystem(self):
        """Fresh copy of the default tree from filesystem.json (top-level dirs)."""
        return copy.deepcopy(_load_default_tree()["dirs"])

    # ------------------------------------------------------------ paths
    def normalize(self, path: str) -> list[str]:
        """Resolve ``path`` against the cwd into absolute path components."""
        path = path.strip()
        if path == "~" or path.startswith("~/"):
            parts = HOME_PATH + path[2:].split("/")
        elif path.startswith("/"):
            parts = path.split("/")
        else:
            parts = self.current_path + path.split("/")
        out: list[str] = []
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                if out:
                    out.pop()
            else:
                out.append(part)
        return out

    def abspath(self, path: str) -> str:
        return "/" + "/".join(self.normalize(path))

    @contextmanager
    def _in_parent(self, path: str):
        """chdir into ``path``'s parent for the duration; yields the basename or None."""
        parts = self.normalize(path)
        saved = self.current_path[:]
        if not parts or not self._directory_exists(parts[:-1]):
            yield None
            return
        self.current_path = parts[:-1]
        try:
            yield parts[-1]
        finally:
            self.current_path = saved

    @staticmethod
    def _missing_parent_result(method_name: str, name: str):
        if method_name in ("file_exists", "check_permission"):
            return False
        if method_name in ("get_permissions",):
            return None
        if method_name == "get_file_owner":
            return None
        return (False, f"{name}: No such file or directory")

    def _resolve_destination(self, source: str, destination: str) -> str:
        """Absolute destination path; a directory destination keeps the source's name."""
        base = source.rstrip("/").rsplit("/", 1)[-1]
        if destination.endswith("/") or self.is_directory_path(destination):
            return self.abspath(destination).rstrip("/") + "/" + base
        return self.abspath(destination)

    def is_directory_path(self, path: str) -> bool:
        return self._directory_exists(self.normalize(path))

    def exists(self, path: str) -> bool:
        return self.is_directory_path(path) or self.file_exists(path)

    def _node_at(self, parts):
        """Default-tree node for absolute ``parts`` (root is ``{'dirs': tree}``), or None."""
        node = {"dirs": self.filesystem}
        for name in parts:
            node = node.get("dirs", {}).get(name)
            if node is None:
                return None
        return node

    def get_current_directory(self):
        """Default-tree node for the cwd. User-created directories have no default node."""
        node = self._node_at(self.current_path)
        return node if node is not None else {}

    def _child(self, name: str) -> str:
        """Absolute path of ``name`` inside the cwd (root-safe: no '//')."""
        return self.get_pwd().rstrip('/') + '/' + name

    def get_pwd(self):
        """Get current working directory as string"""
        return '/' + '/'.join(self.current_path)

    def change_directory(self, path):
        """Change directory. Returns (success, error_message)."""
        if not path:
            self.current_path = HOME_PATH[:]
            return (True, None)
        target = self.normalize(path)
        if self._directory_exists(target):
            self.current_path = target
            return (True, None)
        if self.file_exists(path):
            return (False, f"cd: {path}: Not a directory")
        return (False, f"cd: {path}: No such file or directory")

    def _directory_exists(self, path_list):
        """True if ``path_list`` names a default or user-created directory."""
        if path_list and "/" + "/".join(path_list) + "/" in self.user_created_dirs:
            return True
        return self._node_at(path_list) is not None

    # === Mutable Filesystem Operations ===

    def _get_user_files_size(self):
        """Calculate total size of user-created content"""
        total = 0
        for content in self.user_created_files.values():
            if isinstance(content, list):
                # Convert to string to handle non-string content (e.g., integers)
                total += sum(len(str(line)) for line in content)
            else:
                total += len(str(content))
        for content in self.user_modified_files.values():
            if isinstance(content, list):
                # Convert to string to handle non-string content (e.g., integers)
                total += sum(len(str(line)) for line in content)
            else:
                total += len(str(content))
        return total

    @_path_aware
    def file_exists(self, filename):
        """
        Check if a file exists in the current directory

        Args:
            filename: Name of file to check

        Returns:
            bool: True if file exists, False otherwise
        """
        full_path = self._child(filename)

        # Check if it's been deleted
        if full_path in self.user_deleted_files:
            return False

        # Check user-created files
        if full_path in self.user_created_files:
            return True

        # Check user-modified files
        if full_path in self.user_modified_files:
            return True

        # Check default files
        current_dir = self.get_current_directory()
        if 'files' in current_dir and filename in current_dir['files']:
            return True

        return False

    @_path_aware
    def create_file(self, filename, content=""):
        """
        Create a new file in current directory

        Args:
            filename: Name of file to create
            content: Initial content (string or list of strings)

        Returns:
            tuple: (success, error_message or None)
        """
        if self.file_exists(filename):
            return (False, f"File '{filename}' already exists")

        # Check size limit
        content_size = len(content) if isinstance(content, str) else sum(len(line) for line in content)
        if self._get_user_files_size() + content_size > self.MAX_USER_FILES_SIZE:
            return (False, "File size limit exceeded (16KB max for user files)")

        full_path = self._child(filename)
        self.user_created_files[full_path] = content if content else []
        # Set initial timestamps for new file
        now = datetime.now().isoformat()
        self.file_timestamps[full_path] = {
            'access': now,
            'modify': now,
            'change': now
        }
        return (True, None)

    @_path_aware
    def write_file(self, filename, content, append=False):
        """
        Write content to a file (overwrites or appends)

        Args:
            filename: Name of file
            content: Content to write (string)
            append: If True, append instead of overwrite

        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self._child(filename)

        # Check write permission and ownership for existing files
        if self.file_exists(filename):
            if not self.check_permission(filename, 'w'):
                return (False, f"Permission denied: '{filename}'")
            # Check ownership (only root or owner can write)
            owner = self.get_file_owner(filename)
            if self.current_user != "root" and self.current_user != owner:
                return (False, f"Permission denied: '{filename}' (operation not permitted)")

        # Get existing content
        existing = None
        if full_path in self.user_created_files:
            existing = self.user_created_files[full_path]
        elif full_path in self.user_modified_files:
            existing = self.user_modified_files[full_path]
        elif self.file_exists(filename):
            # Modifying a default file
            success, file_content = self.read_file(filename)
            if success:
                existing = file_content

        # Build new content
        if append and existing:
            if isinstance(existing, list):
                new_content = existing + [content]
            else:
                new_content = existing + '\n' + content
        else:
            new_content = [content] if not isinstance(content, list) else content

        # Check size (convert to string to handle non-string content)
        new_size = sum(len(str(line)) for line in new_content) if isinstance(new_content, list) else len(str(new_content))
        # Subtract old content size since it's already counted in _get_user_files_size()
        old_size = 0
        if full_path in self.user_created_files:
            old_content = self.user_created_files[full_path]
            old_size = sum(len(str(line)) for line in old_content) if isinstance(old_content, list) else len(str(old_content))
        elif full_path in self.user_modified_files:
            old_content = self.user_modified_files[full_path]
            old_size = sum(len(str(line)) for line in old_content) if isinstance(old_content, list) else len(str(old_content))
        if self._get_user_files_size() - old_size + new_size > self.MAX_USER_FILES_SIZE:
            return (False, "File size limit exceeded (16KB max for user files)")

        # Write to appropriate location
        if full_path in self.user_created_files:
            self.user_created_files[full_path] = new_content
        else:
            self.user_modified_files[full_path] = new_content

        # Update modify and change timestamps
        self._update_timestamp(full_path, 'modify')
        self._update_timestamp(full_path, 'change')

        return (True, None)

    @_path_aware
    def delete_file(self, filename):
        """
        Delete a file from current directory

        Args:
            filename: Name of file to delete

        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self._child(filename)

        # Check write permission and ownership (needed to delete)
        if not self.check_permission(filename, 'w'):
            return (False, f"Permission denied: '{filename}'")
        # Check ownership (only root or owner can delete)
        owner = self.get_file_owner(filename)
        if self.current_user != "root" and self.current_user != owner:
            return (False, f"Permission denied: '{filename}' (operation not permitted)")

        # Delete user-created files
        if full_path in self.user_created_files:
            del self.user_created_files[full_path]
            return (True, None)
        elif full_path in self.user_modified_files:
            del self.user_modified_files[full_path]
            return (True, None)
        elif self.file_exists(filename):
            # Mark default file as deleted (can be undone with rm save)
            self.user_deleted_files.add(full_path)
            return (True, None)
        else:
            return (False, f"File '{filename}' not found")

    @_path_aware
    def create_directory(self, dirname):
        """
        Create a new directory in current location

        Args:
            dirname: Name of directory to create

        Returns:
            tuple: (success, error_message or None)
        """
        current_dir = self.get_current_directory()
        if 'dirs' in current_dir and dirname in current_dir['dirs']:
            return (False, f"Directory '{dirname}' already exists")

        full_path = self._child(dirname)
        # Ensure trailing slash for directories
        if not full_path.endswith('/'):
            full_path = full_path + '/'
        if full_path in self.user_created_dirs:
            return (False, f"Directory '{dirname}' already exists")

        self.user_created_dirs.append(full_path)
        # Set initial timestamps for new directory (use path without trailing slash for consistency)
        now = datetime.now().isoformat()
        dir_path_no_slash = full_path.rstrip('/')
        self.file_timestamps[dir_path_no_slash] = {
            'access': now,
            'modify': now,
            'change': now
        }
        return (True, None)

    @_path_aware
    def delete_directory(self, dirname):
        """
        Delete an empty user-created directory

        Args:
            dirname: Name of directory to delete

        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self._child(dirname)
        # Ensure trailing slash to match how user_created_dirs stores paths
        full_path_with_slash = full_path if full_path.endswith('/') else full_path + '/'

        if full_path_with_slash not in self.user_created_dirs:
            return (False, "Cannot delete: not a user-created directory")

        # Check if empty
        for file_path in self.user_created_files:
            if file_path.startswith(full_path_with_slash):
                return (False, "Directory not empty")

        self.user_created_dirs.remove(full_path_with_slash)
        return (True, None)

    def read_file_at_path(self, path):
        """
        Read a file given a relative or absolute path (e.g., 'data/secret/file.txt', '/var/log/boot.log').
        Temporarily navigates to the file's parent directory, reads the file, and restores the original directory.

        Args:
            path: Relative or absolute path to the file

        Returns:
            tuple: (success: bool, content: list of strings or error message)
        """
        if '/' not in path:
            # Simple filename in current directory
            return self.read_file(path)

        saved = self.current_path[:]
        try:
            # Split into directory and filename
            last_slash = path.rfind('/')
            dir_part = path[:last_slash] if last_slash > 0 else '/'
            filename = path[last_slash + 1:]

            if not filename:
                return (False, f"cat: {path}: Is a directory")

            success, error = self.change_directory(dir_part)
            if not success:
                return (False, f"cat: {path}: No such file or directory")

            return self.read_file(filename)
        finally:
            self.current_path = saved

    def list_directory_at_path(self, path, show_hidden=False):
        """
        List directory contents at an arbitrary path.

        Args:
            path: Relative or absolute path to the directory
            show_hidden: If True, include hidden files/directories

        Returns:
            tuple: (success: bool, contents: list of names or error message)
        """
        saved = self.current_path[:]
        try:
            success, error = self.change_directory(path)
            if not success:
                return (False, f"ls: cannot access '{path}': No such file or directory")
            contents = self.list_directory(show_hidden=show_hidden)
            return (True, contents)
        finally:
            self.current_path = saved

    def is_directory(self, name):
        """
        Check if a name refers to a directory in the current location.

        Args:
            name: Name or path to check

        Returns:
            bool: True if it's a directory
        """
        name = name.rstrip('/')

        # Check if it's an absolute or relative path we can cd into
        if '/' in name:
            saved = self.current_path[:]
            try:
                success, _ = self.change_directory(name)
                return success
            finally:
                self.current_path = saved

        # Check current directory's subdirs
        current_dir = self.get_current_directory()
        if 'dirs' in current_dir and name in current_dir['dirs']:
            return True

        # Check user-created directories
        full_path = self._child(name + '/')
        if full_path in self.user_created_dirs:
            return True

        return False

    def copy_file(self, source, destination):
        """Copy file; ``destination`` may be a path or an existing directory."""
        return self._copy_file(source, self._resolve_destination(source, destination))

    @_path_aware
    def _copy_file(self, source, destination):
        """
        Copy a file from source to destination.

        Args:
            source: Source filename (in current directory)
            destination: Destination filename or path

        Returns:
            tuple: (success, error_message or None)
        """
        # Read source file content
        if not self.file_exists(source):
            return (False, f"cp: cannot stat '{source}': No such file or directory")

        if not self.check_permission(source, 'r'):
            return (False, f"cp: cannot open '{source}': Permission denied")

        success, content = self.read_file(source)
        if not success:
            return (False, f"cp: cannot read '{source}': {content}")

        # Get source permissions
        source_perms = self.get_permissions(source)

        # Resolve destination
        if '/' in destination:
            dest_parts = destination.rsplit('/', 1)
            dest_dir = dest_parts[0] or '/'
            dest_filename = dest_parts[1] if dest_parts[1] else source

            saved = self.current_path[:]
            success_cd, error = self.change_directory(dest_dir)
            if not success_cd:
                self.current_path = saved
                return (False, f"cp: target '{dest_dir}': No such file or directory")

            if self.file_exists(dest_filename):
                self.current_path = saved
                return (False, f"cp: '{destination}' already exists")

            result = self.create_file(dest_filename, content)
            if result[0] and source_perms and source_perms != "rwxrwxrwx":
                dest_full = self._child(dest_filename)
                self.file_permissions[dest_full] = source_perms
            self.current_path = saved
            return result
        else:
            if self.file_exists(destination):
                return (False, f"cp: '{destination}' already exists")

            result = self.create_file(destination, content)
            if result[0] and source_perms and source_perms != "rwxrwxrwx":
                dest_full = self._child(destination)
                self.file_permissions[dest_full] = source_perms
            return result

    @_path_aware
    def delete_directory_recursive(self, dirname):
        """
        Recursively delete a user-created directory and all its contents.
        Only works on user-created directories.

        Args:
            dirname: Name of directory to delete

        Returns:
            tuple: (success, error_message or None)
        """
        full_path = self._child(dirname)
        full_path_with_slash = full_path if full_path.endswith('/') else full_path + '/'

        if full_path_with_slash not in self.user_created_dirs:
            return (False, f"rm: cannot remove '{dirname}': Not a user-created directory")

        # Remove all user-created files under this directory
        files_to_remove = [f for f in self.user_created_files if f.startswith(full_path_with_slash)]
        for f in files_to_remove:
            del self.user_created_files[f]
            if f in self.file_permissions:
                del self.file_permissions[f]
            if f in self.file_owners:
                del self.file_owners[f]

        # Remove all user-created subdirectories
        dirs_to_remove = [d for d in self.user_created_dirs if d.startswith(full_path_with_slash)]
        dirs_to_remove.append(full_path_with_slash)
        for d in dirs_to_remove:
            self.user_created_dirs.remove(d)

        return (True, None)

    def _walk_recursive(self, dir_path):
        """Internal recursive walk helper. Yields (dirpath, dirnames, filenames)."""
        saved = self.current_path[:]
        self.change_directory(dir_path)

        items = self.list_directory(show_hidden=True)
        dirnames = [i.rstrip('/') for i in items if i.endswith('/')]
        filenames = [i for i in items if not i.endswith('/')]

        yield (dir_path, dirnames, filenames)

        for d in dirnames:
            child_path = dir_path.rstrip('/') + '/' + d
            yield from self._walk_recursive(child_path)

        self.current_path = saved

    def walk_directory(self, path=None):
        """
        Recursively walk a directory tree, yielding (dirpath, dirnames, filenames).

        Args:
            path: Starting path (None = current directory)

        Yields:
            tuple: (dirpath, dirnames, filenames)
        """
        saved = self.current_path[:]
        try:
            if path:
                success, _ = self.change_directory(path)
                if not success:
                    return

            yield from self._walk_recursive(self.get_pwd())
        finally:
            self.current_path = saved

    @_path_aware
    def get_permissions(self, filename):
        """
        Get file or directory permissions

        Args:
            filename: Name of file or directory (may have trailing / for dirs)

        Returns:
            str: Permission string like "rwx" (3 chars) or "rwxrwxrwx" (9 chars), or None if file/dir doesn't exist
        """
        # Normalize directory paths (remove trailing slash for lookup)
        name = filename.rstrip('/')
        full_path = self._child(name)

        # Check if it's a directory
        is_dir = False
        current_dir = self.get_current_directory()
        if 'dirs' in current_dir and name in current_dir['dirs']:
            is_dir = True
        elif full_path + '/' in self.user_created_dirs:
            is_dir = True

        # Check if file/directory exists
        if not is_dir and not self.file_exists(filename):
            return None

        # Return custom permissions if set by user (via chmod) - highest priority
        if full_path in self.file_permissions:
            perms = self.file_permissions[full_path]
            # Expand 3-char to 9-char if needed
            if len(perms) == 3:
                return perms + perms + perms
            return perms

        # For directories, check default filesystem structure for permissions
        if is_dir and 'dirs' in current_dir and name in current_dir['dirs']:
            dir_entry = current_dir['dirs'][name]
            if isinstance(dir_entry, dict) and 'permissions' in dir_entry:
                perms = dir_entry['permissions']
                # Expand 3-char to 9-char if needed
                if len(perms) == 3:
                    return perms + perms + perms
                return perms

        # Check default filesystem structure for file permissions
        if not is_dir and 'files' in current_dir and name in current_dir['files']:
            file_entry = current_dir['files'][name]
            return self._extract_file_permissions(file_entry, name, full_path)

        # For user-created/modified files and directories, default to 'rwxrwxrwx'
        return "rwxrwxrwx"

    @_path_aware
    def get_file_owner(self, filename):
        """
        Get the owner of a file or directory

        Args:
            filename: Name of file or directory (may have trailing / for dirs)

        Returns:
            str: Owner username ("pilot" or "root"), or current user if not specified
        """
        # Strip trailing slash if present (for directories)
        name = filename.rstrip('/')

        # Handle current directory (.)
        if name == '.' or name == '':
            full_path = self.get_pwd()
        else:
            full_path = self._child(name)

        # Normalize double slashes at root
        full_path = full_path.replace('//', '/')

        # Check if file has a defined owner (moved/modified files)
        if full_path in self.file_owners:
            return self.file_owners[full_path]

        # Check default file owners
        if full_path in self.default_file_owners:
            return self.default_file_owners[full_path]

        # Default: files are owned by the current user
        return self.current_user

    def set_user(self, username):
        """
        Set the current user (for sudo implementation)

        Args:
            username: "pilot" or "root"
        """
        self.current_user = username

    def get_current_user(self):
        """Get the current username"""
        return self.current_user

    @_path_aware
    def set_permissions(self, filename, permissions):
        """
        Set file or directory permissions (chmod)

        Args:
            filename: Name of file or directory (may have trailing / for dirs)
            permissions: Permission string or octal mode

        Returns:
            tuple: (success, error_message or None)
        """
        # Normalize directory paths (remove trailing slash for storage)
        name = filename.rstrip('/')
        full_path = self._child(name)

        # Check if file or directory exists
        current_dir = self.get_current_directory()
        is_dir = False
        if 'dirs' in current_dir and name in current_dir['dirs']:
            is_dir = True
        elif full_path + '/' in self.user_created_dirs:
            is_dir = True

        if not is_dir and not self.file_exists(filename):
            return (False, f"chmod: cannot access '{filename}': No such file or directory")

        # Check ownership (only root or owner can chmod)
        owner = self.get_file_owner(filename)
        if self.current_user != "root" and self.current_user != owner:
            return (False, f"chmod: changing permissions of '{filename}': Operation not permitted")

        # Parse permissions
        if not permissions.isdigit() and _SYMBOLIC_MODE.match(permissions.split(",")[0]) \
                and not (len(permissions) in (3, 9) and all(c in 'rwx-' for c in permissions)):
            current = self.get_permissions(filename) or "rw-r--r--"
            new_perms = apply_symbolic_mode(current, permissions)
            if new_perms is None:
                return (False, f"chmod: invalid mode: '{permissions}'")
            permissions = new_perms
        elif permissions.isdigit():
            # Octal format (e.g., "644", "755", "0755", "7", "777")
            try:
                # Handle 4-digit octal (leading 0) or 3-digit or single digit
                if len(permissions) == 4 and permissions[0] == '0':
                    # 4-digit octal like "0755" - use the 3 digits after the leading 0
                    # Parse all three: user, group, other
                    user_mode = int(permissions[1])
                    group_mode = int(permissions[2])
                    other_mode = int(permissions[3])

                    def mode_to_str(mode):
                        s = ""
                        s += "r" if mode & 4 else "-"
                        s += "w" if mode & 2 else "-"
                        s += "x" if mode & 1 else "-"
                        return s

                    permissions = mode_to_str(user_mode) + mode_to_str(group_mode) + mode_to_str(other_mode)
                elif len(permissions) == 1:
                    # Single digit - treat as user permissions only (3 characters)
                    mode = int(permissions)
                    perm_str = ""
                    perm_str += "r" if mode & 4 else "-"
                    perm_str += "w" if mode & 2 else "-"
                    perm_str += "x" if mode & 1 else "-"
                    permissions = perm_str
                elif len(permissions) == 3:
                    # 3-digit octal: user, group, other - create full 9-character string
                    user_mode = int(permissions[0])
                    group_mode = int(permissions[1])
                    other_mode = int(permissions[2])

                    def mode_to_str(mode):
                        s = ""
                        s += "r" if mode & 4 else "-"
                        s += "w" if mode & 2 else "-"
                        s += "x" if mode & 1 else "-"
                        return s

                    permissions = mode_to_str(user_mode) + mode_to_str(group_mode) + mode_to_str(other_mode)
                else:
                    return (False, f"chmod: invalid mode: '{permissions}' (must be 1-4 digits)")
            except (ValueError, IndexError):
                return (False, f"chmod: invalid mode: '{permissions}'")
        elif len(permissions) == 3 and all(c in 'rwx-' for c in permissions):
            # Symbolic format (e.g., "rwx", "rw-", "r--") - 3 characters, user only
            pass
        elif len(permissions) == 9 and all(c in 'rwx-' for c in permissions):
            # Full 9-character format (e.g., "rwxrwxrwx")
            pass
        else:
            return (False, f"chmod: invalid mode: '{permissions}'")

        # Set permissions
        self.file_permissions[full_path] = permissions
        # Update change timestamp (metadata changed)
        self._update_timestamp(full_path, 'change')
        return (True, None)

    @_path_aware
    def check_permission(self, filename, permission):
        """
        Check if user has a specific permission on a file

        Args:
            filename: Name of file
            permission: 'r' for read, 'w' for write, 'x' for execute

        Returns:
            bool: True if permission is granted, False otherwise
        """
        # If file doesn't exist, we can't check permissions
        # Return False to be safe (caller should check file_exists first)
        if not self.file_exists(filename):
            return False

        perms = self.get_permissions(filename)
        if perms is None:
            return False

        perm_map = {'r': 0, 'w': 1, 'x': 2}
        if permission not in perm_map:
            return False

        perm_index = perm_map[permission]

        # Determine which permission set to check based on user's relationship to file
        owner = self.get_file_owner(filename)

        # Root always has all permissions
        if self.current_user == "root":
            return True

        # Check which permission group applies
        if len(perms) == 9:
            # 9-character format: user, group, other
            if self.current_user == owner:
                # User is owner - check user permissions (positions 0-2)
                check_index = perm_index
            else:
                # For simplicity, if not owner, check other permissions (positions 6-8)
                # In a full system, we'd check group membership first
                check_index = 6 + perm_index
        else:
            # 3-character format: only user permissions
            # If user is owner, check permissions; otherwise deny
            if self.current_user == owner:
                check_index = perm_index
            else:
                return False

        # Check if permission is granted
        if check_index >= len(perms):
            return False
        return perms[check_index] == permission

    def move_file(self, source, destination):
        """Move file; ``destination`` may be a path or an existing directory."""
        return self._move_file(source, self._resolve_destination(source, destination))

    @_path_aware
    def _move_file(self, source, destination):
        """
        Move or rename a file (including default system files)

        Args:
            source: Source filename (in current directory)
            destination: Destination path (can include directory path or just filename)

        Returns:
            tuple: (success, error_message or None)
        """
        source_full = self._child(source)

        # Check if source exists
        if not self.file_exists(source):
            return (False, f"File '{source}' not found")

        # Check ownership (only root or owner can move)
        owner = self.get_file_owner(source)
        if self.current_user != "root" and self.current_user != owner:
            return (False, f"Permission denied: '{source}' (operation not permitted)")

        # Read source file content
        success, content = self.read_file(source)
        if not success:
            return (False, f"Cannot read source file: {source}")

        # Compute destination full path
        if '/' in destination:
            # Destination includes directory path
            dest_parts = destination.rsplit('/', 1)
            dest_dir = dest_parts[0] or '/'
            dest_filename = dest_parts[1]

            # Validate destination directory exists
            old_path = self.current_path[:]
            success, error = self.change_directory(dest_dir)
            if not success:
                self.current_path = old_path
                return (False, f"Destination directory not found: {dest_dir}")

            dest_full = self._child(dest_filename)
            self.current_path = old_path

            # Check if destination file already exists
            old_path = self.current_path[:]
            self.change_directory(dest_dir)
            dest_exists = self.file_exists(dest_filename)
            self.current_path = old_path

            if dest_exists:
                return (False, f"Destination file already exists: {destination}")
        else:
            # Destination is in current directory (rename)
            dest_full = self._child(destination)
            if self.file_exists(destination):
                return (False, f"Destination file already exists: {destination}")

        # Determine if source is a default file
        is_default = (source_full not in self.user_created_files and
                     source_full not in self.user_modified_files)

        # Get source permissions and ownership before moving
        source_permissions = None
        source_owner = None
        if is_default:
            # Get permissions from default filesystem structure
            source_dir = self.get_current_directory()
            if 'files' in source_dir and source in source_dir['files']:
                file_entry = source_dir['files'][source]
                source_permissions = self._extract_file_permissions(file_entry, source, source_full)
            # Get ownership from default_file_owners
            source_owner = self.get_file_owner(source)
        elif source_full in self.file_permissions:
            # Get user-set permissions
            source_permissions = self.file_permissions[source_full]
            # Get ownership (could be from file_owners or default_file_owners)
            source_owner = self.get_file_owner(source)
        else:
            # Default permissions for user-created files
            source_permissions = "rwxrwxrwx"
            # Get ownership
            source_owner = self.get_file_owner(source)

        # Perform the move
        if source_full in self.user_created_files:
            del self.user_created_files[source_full]
            # Preserve permissions if they were set
            if source_full in self.file_permissions:
                source_permissions = self.file_permissions[source_full]
                del self.file_permissions[source_full]
            # Preserve ownership if it was explicitly set
            if source_full in self.file_owners:
                source_owner = self.file_owners[source_full]
                del self.file_owners[source_full]
        elif source_full in self.user_modified_files:
            del self.user_modified_files[source_full]
            # Preserve permissions if they were set
            if source_full in self.file_permissions:
                source_permissions = self.file_permissions[source_full]
                del self.file_permissions[source_full]
            # Preserve ownership if it was explicitly set
            if source_full in self.file_owners:
                source_owner = self.file_owners[source_full]
                del self.file_owners[source_full]
        elif is_default:
            # Mark default file as deleted from source location
            self.user_deleted_files.add(source_full)

        # Create file at destination
        self.user_created_files[dest_full] = content

        # Preserve permissions at destination (unless they're the default 'rwxrwxrwx')
        if source_permissions and source_permissions != "rwxrwxrwx":
            self.file_permissions[dest_full] = source_permissions

        # Preserve ownership at destination
        # Always preserve if source was root-owned (security: prevent privilege escalation)
        # Also preserve if source was explicitly set in file_owners
        if source_owner:
            # Preserve if:
            # 1. Source is root-owned (security requirement)
            # 2. Source ownership was explicitly set (moved/modified file)
            # 3. Source owner differs from current user (non-default ownership)
            if source_owner == 'root' or source_full in self.file_owners or source_owner != self.current_user:
                self.file_owners[dest_full] = source_owner

        return (True, None)

    def list_directory(self, show_hidden=False):
        """
        List contents of current directory (including user-created)

        Args:
            show_hidden: If True, include files/directories starting with '.' (hidden files)

        Returns:
            list: List of file and directory names
        """
        current_dir = self.get_current_directory()
        contents = []
        current_path = self.get_pwd().rstrip('/')

        # Add default directories
        if 'dirs' in current_dir:
            for dir_name in sorted(current_dir['dirs'].keys()):
                # Skip metadata keys that might have been incorrectly added as directories
                if dir_name not in ('files', 'dirs'):
                    if show_hidden or not dir_name.startswith('.'):
                        contents.append(f"{dir_name}/")

        # Add user-created directories
        for dir_path in sorted(self.user_created_dirs):
            # Stored with a trailing slash ("/a/b/"); compare the parent of "/a/b".
            parent, _, dir_name = dir_path.rstrip('/').rpartition('/')
            if dir_name:
                if parent == current_path:
                    if show_hidden or not dir_name.startswith('.'):
                        if f"{dir_name}/" not in contents:
                            contents.append(f"{dir_name}/")

        # Add default files (excluding deleted ones)
        if 'files' in current_dir:
            for file_name in sorted(current_dir['files'].keys()):
                full_path = current_path + '/' + file_name
                if full_path not in self.user_deleted_files:
                    if show_hidden or not file_name.startswith('.'):
                        contents.append(file_name)

        # Add user-created files in this directory
        for file_path in sorted(self.user_created_files.keys()):
            if '/' in file_path:
                parent = file_path.rsplit('/', 1)[0]
                if parent == current_path:
                    file_name = file_path.rsplit('/', 1)[1]
                    if show_hidden or not file_name.startswith('.'):
                        if file_name not in contents:
                            contents.append(file_name)

        # Add user-modified files
        for file_path in sorted(self.user_modified_files.keys()):
            if '/' in file_path:
                parent = file_path.rsplit('/', 1)[0]
                if parent == current_path:
                    file_name = file_path.rsplit('/', 1)[1]
                    if show_hidden or not file_name.startswith('.'):
                        if file_name not in contents:
                            contents.append(file_name)

        return contents

    @_path_aware
    def read_file(self, filename):
        """Read a file (checks user files first, then defaults)"""
        full_path = self._child(filename)

        # Check if file has been deleted
        if full_path in self.user_deleted_files:
            return (False, f"File '{filename}' not found")

        # Check user-modified files first
        if full_path in self.user_modified_files:
            # Check read permission for existing files
            if not self.check_permission(filename, 'r'):
                return (False, f"Permission denied: '{filename}'")
            content = self.user_modified_files[full_path]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])

        # Check user-created files
        if full_path in self.user_created_files:
            # Check read permission for existing files
            if not self.check_permission(filename, 'r'):
                return (False, f"Permission denied: '{filename}'")
            content = self.user_created_files[full_path]
            if isinstance(content, list):
                return (True, content)
            else:
                return (True, [content])

        # Fall back to default files
        current_dir = self.get_current_directory()

        if 'files' in current_dir and filename in current_dir['files']:
            # Check if file has been deleted
            if full_path in self.user_deleted_files:
                return (False, f"cat: {filename}: No such file")
            # Check read permission for existing default files
            if not self.check_permission(filename, 'r'):
                return (False, f"Permission denied: '{filename}'")
            file_entry = current_dir['files'][filename]
            content = self._extract_file_content(file_entry)
            return (True, content)
        else:
            # File doesn't exist - don't check permissions for non-existent files
            return (False, f"cat: {filename}: No such file")

    # === Save/Load State ===

    def get_state(self):
        """Get filesystem state for saving"""
        return {
            # Note: current_path is NOT saved - always start in home directory
            'user_created_files': self.user_created_files,
            'user_created_dirs': self.user_created_dirs,
            'user_modified_files': self.user_modified_files,
            'user_deleted_files': list(self.user_deleted_files),
            'file_permissions': self.file_permissions,
            'file_owners': self.file_owners,
            'file_timestamps': self.file_timestamps,
            # Note: current_user is NOT saved - always start as 'pilot'
        }

    def _restore_state(self, state):
        """Restore filesystem state from save"""
        # Note: current_path is never restored - always start in home directory
        # Note: current_user is never restored - always start as 'pilot'
        if 'user_created_files' in state:
            self.user_created_files = state['user_created_files']
        if 'user_created_dirs' in state:
            self.user_created_dirs = state['user_created_dirs']
        if 'user_modified_files' in state:
            self.user_modified_files = state['user_modified_files']
        if 'user_deleted_files' in state:
            self.user_deleted_files = set(state['user_deleted_files'])
        if 'file_permissions' in state:
            self.file_permissions = state['file_permissions']
        if 'file_owners' in state:
            self.file_owners = state['file_owners']
        if 'file_timestamps' in state:
            self.file_timestamps = state['file_timestamps']
        else:
            # Initialize timestamps for restored files if not present
            self._initialize_default_timestamps()

    def reset_to_defaults(self):
        """Reset filesystem to default state"""
        self.current_path = ['home', 'pilot', 'blthll']
        self.user_created_files = {}
        self.user_created_dirs = []
        self.user_modified_files = {}
        self.user_deleted_files = set()
        self.file_permissions = {}
        self.file_owners = {}
        self.file_timestamps = {}
        self.current_user = "pilot"
        # Re-initialize default timestamps
        self._initialize_default_timestamps()

    def reset_filesystem_keep_user_files(self):
        """
        Reset filesystem to defaults but preserve user-created files.
        Moves all user-created files to the starting directory (blthll).
        """
        # Save user-created files
        saved_files = {}

        # Collect all user-created files
        for path, content in self.user_created_files.items():
            # Extract just the filename
            path_parts = path.strip('/').split('/')
            filename = path_parts[-1]
            # Save to blthll directory
            new_path = '/home/pilot/blthll/' + filename
            saved_files[new_path] = content

        # Collect user-created directories (but we'll just keep files for now)
        # Directories are more complex, so we'll skip them for simplicity

        # Reset everything
        self.reset_to_defaults()

        # Restore user-created files to blthll
        self.user_created_files = saved_files

    def _get_default_file_paths(self):
        """
        Build a map of all default files and their paths.
        Returns: dict mapping (normalized content) -> list of paths where that file exists
        """
        file_map = {}

        def traverse(node, current_path):
            """Recursively traverse the filesystem tree"""
            if 'files' in node:
                for filename, file_entry in node['files'].items():
                    full_path = current_path + '/' + filename
                    # Extract content from file entry (handles both list and dict formats)
                    content = self._extract_file_content(file_entry)
                    # Normalize content for comparison
                    content_key = tuple(content)

                    if content_key not in file_map:
                        file_map[content_key] = []
                    file_map[content_key].append(full_path)

            if 'dirs' in node:
                for dirname, subnode in node['dirs'].items():
                    traverse(subnode, current_path + '/' + dirname)

        # Traverse from root
        for top_level, node in self.filesystem.items():
            if isinstance(node, dict):
                traverse(node, '/' + top_level)

        return file_map

    def _get_default_files_in_directory(self, dir_path):
        """
        Get list of default files that should exist in a directory.
        Returns: list of (filename, full_path) tuples
        """
        # Convert path string to path list
        if dir_path.startswith('/'):
            path_parts = [p for p in dir_path.split('/') if p]
        else:
            path_parts = dir_path.split('/')
            path_parts = [p for p in path_parts if p]

        # Navigate to directory
        current = self.filesystem
        for part in path_parts:
            if part in current:
                current = current[part]
            elif 'dirs' in current and part in current['dirs']:
                current = current['dirs'][part]
            else:
                return []  # Directory doesn't exist in default filesystem

        # Get files from this directory
        files = []
        if 'files' in current:
            for filename in current['files'].keys():
                full_path = '/' + '/'.join(path_parts) + '/' + filename
                files.append((filename, full_path))

        return files

    def reset_directory(self, dir_path):
        """
        Reset a directory to its default state.

        Args:
            dir_path: Directory path (e.g., '/home/pilot/blthll/data' or 'data')

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        # Normalize directory path
        if not dir_path.startswith('/'):
            # Relative path - make it absolute from current directory
            current_pwd = self.get_pwd()
            if dir_path == '.':
                dir_path = current_pwd
            elif dir_path == '..':
                # Parent directory
                if len(self.current_path) > 0:
                    parent_parts = self.current_path[:-1]
                    dir_path = '/' + '/'.join(parent_parts) if parent_parts else '/'
                else:
                    return (False, "Already at root directory")
            else:
                dir_path = current_pwd + '/' + dir_path

        # Ensure path ends without trailing slash (except root)
        if dir_path != '/' and dir_path.endswith('/'):
            dir_path = dir_path[:-1]

        # Get default files that should be in this directory
        default_files = self._get_default_files_in_directory(dir_path)

        # Build map of default file contents to their paths
        default_file_map = self._get_default_file_paths()

        # 1. Remove all files in user_created_files in this directory
        # (These are either user-created files or moved default files)
        files_to_remove = []
        for file_path in list(self.user_created_files.keys()):
            if file_path.startswith(dir_path + '/'):
                files_to_remove.append(file_path)

        # For moved default files, we need to restore them to their original location
        # by removing them from user_deleted_files at the original path
        for file_path in files_to_remove:
            content = self.user_created_files[file_path]
            if isinstance(content, list):
                content_key = tuple(content)
            else:
                content_key = (content,)

            # Check if this is a moved default file
            if content_key in default_file_map:
                # Find the original location(s) of this file
                original_paths = default_file_map[content_key]
                # Remove from user_deleted_files at original locations
                for orig_path in original_paths:
                    if orig_path in self.user_deleted_files:
                        self.user_deleted_files.remove(orig_path)

            # Remove from user_created_files
            del self.user_created_files[file_path]
            # Remove permissions if set
            if file_path in self.file_permissions:
                del self.file_permissions[file_path]
            # Remove ownership if set
            if file_path in self.file_owners:
                del self.file_owners[file_path]

        # 3. Restore deleted default files from this directory
        for _filename, full_path in default_files:
            if full_path in self.user_deleted_files:
                self.user_deleted_files.remove(full_path)

        # 4. Remove user-modified files in this directory (restore to default)
        modified_to_remove = []
        for file_path in list(self.user_modified_files.keys()):
            if file_path.startswith(dir_path + '/'):
                modified_to_remove.append(file_path)

        for file_path in modified_to_remove:
            del self.user_modified_files[file_path]
            # Remove permissions if set
            if file_path in self.file_permissions:
                del self.file_permissions[file_path]
            # Remove ownership if set
            if file_path in self.file_owners:
                del self.file_owners[file_path]

        # 5. Remove user-created directories in this directory
        dirs_to_remove = []
        for dir_path_item in self.user_created_dirs:
            if dir_path_item.startswith(dir_path + '/'):
                dirs_to_remove.append(dir_path_item)

        for dir_path_item in dirs_to_remove:
            self.user_created_dirs.remove(dir_path_item)
            # Remove directory permissions if set (without trailing slash)
            dir_path_no_slash = dir_path_item.rstrip('/')
            if dir_path_no_slash in self.file_permissions:
                del self.file_permissions[dir_path_no_slash]

        # 6. Remove permissions and ownership for files that were removed from user_created_files
        # (These were already removed above, but we need to clean up their metadata)
        perms_to_remove = []
        for perm_path in list(self.file_permissions.keys()):
            if perm_path.startswith(dir_path + '/'):
                perms_to_remove.append(perm_path)

        for perm_path in perms_to_remove:
            del self.file_permissions[perm_path]

        # Also clean up ownership
        owners_to_remove = []
        for owner_path in list(self.file_owners.keys()):
            if owner_path.startswith(dir_path + '/'):
                owners_to_remove.append(owner_path)

        for owner_path in owners_to_remove:
            del self.file_owners[owner_path]

        return (True, None)

