"""
Unit tests for Python script execution in restricted environment
"""

import unittest
from src.unix.script_executor import ScriptExecutor
from src.unix.filesystem import VirtualFileSystem


class TestScriptExecutor(unittest.TestCase):
    """Test cases for ScriptExecutor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.executor = ScriptExecutor()
        self.filesystem = VirtualFileSystem()
        self.output_lines = []
        
        # Set up a simple test filesystem
        # Create a test file
        self.filesystem.create_file("test.txt", ["line 1", "line 2", "line 3"])
        self.filesystem.create_file("readme.txt", ["Hello", "World"])
        
        # Track output
        def output_callback(line):
            self.output_lines.append(line)
        
        self.output_callback = output_callback
    
    def test_open_read(self):
        """Test reading a file with open()"""
        code = """
with open('test.txt', 'r') as f:
    content = f.read()
    print(content)
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        self.assertIn("line 1", self.output_lines[0])
        self.assertIn("line 2", self.output_lines[1])
        self.assertIn("line 3", self.output_lines[2])
    
    def test_open_write(self):
        """Test writing a file with open()"""
        code = """
with open('output.txt', 'w') as f:
    f.write('Hello, World!\\n')
    f.write('This is a test\\n')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        
        # Verify file was created
        success, content = self.filesystem.read_file("output.txt")
        self.assertTrue(success)
        self.assertIn("Hello, World!", content)
        self.assertIn("This is a test", content)
    
    def test_open_append(self):
        """Test appending to a file with open()"""
        code = """
with open('test.txt', 'a') as f:
    f.write('line 4\\n')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        
        # Verify content was appended
        success, content = self.filesystem.read_file("test.txt")
        self.assertTrue(success)
        self.assertEqual(len(content), 4)
        self.assertEqual(content[3], "line 4")
    
    def test_open_readlines(self):
        """Test reading lines with readlines()"""
        code = """
with open('test.txt', 'r') as f:
    lines = f.readlines()
    for line in lines:
        print(line.strip())
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        self.assertGreaterEqual(len(self.output_lines), 3)
    
    def test_os_getcwd(self):
        """Test os.getcwd()"""
        code = """
import os
cwd = os.getcwd()
print(cwd)
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        self.assertIn("/home/pilot/blthll", self.output_lines[0])
    
    def test_os_listdir(self):
        """Test os.listdir()"""
        code = """
import os
files = os.listdir()
for f in sorted(files):
    print(f)
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        # Should list test files
        output_str = " ".join(self.output_lines)
        self.assertIn("test.txt", output_str)
    
    def test_os_path_exists(self):
        """Test os.path.exists()"""
        code = """
import os.path
if os.path.exists('test.txt'):
    print('test.txt exists')
if not os.path.exists('nonexistent.txt'):
    print('nonexistent.txt does not exist')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("test.txt exists", output_str)
        self.assertIn("nonexistent.txt does not exist", output_str)
    
    def test_os_path_getsize(self):
        """Test os.path.getsize()"""
        code = """
import os.path
size = os.path.getsize('test.txt')
print(f'Size: {size} bytes')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("Size:", output_str)
        self.assertIn("bytes", output_str)
    
    def test_os_stat(self):
        """Test os.stat()"""
        code = """
import os
stat_info = os.stat('test.txt')
print(f'Size: {stat_info.st_size}')
print(f'Mode: {stat_info.st_mode}')
print(f'Owner: {stat_info.st_uid}')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("Size:", output_str)
        self.assertIn("Mode:", output_str)
        self.assertIn("Owner:", output_str)
    
    def test_os_stat_file_not_found(self):
        """Test os.stat() raises FileNotFoundError for missing file"""
        code = """
import os
try:
    os.stat('nonexistent.txt')
    print('ERROR: Should have raised FileNotFoundError')
except FileNotFoundError as e:
    print('FileNotFoundError raised correctly')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("FileNotFoundError raised correctly", output_str)
        self.assertNotIn("ERROR", output_str)
    
    def test_os_access(self):
        """Test os.access()"""
        code = """
import os
if os.access('test.txt', os.F_OK):
    print('File exists')
if os.access('test.txt', os.R_OK):
    print('File is readable')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("File exists", output_str)
        self.assertIn("File is readable", output_str)
    
    def test_os_remove(self):
        """Test os.remove()"""
        code = """
import os
os.remove('readme.txt')
print('File removed')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        
        # Verify file was deleted
        exists = self.filesystem.file_exists("readme.txt")
        self.assertFalse(exists)
    
    def test_os_remove_file_not_found(self):
        """Test os.remove() raises FileNotFoundError for missing file"""
        code = """
import os
try:
    os.remove('nonexistent.txt')
    print('ERROR: Should have raised FileNotFoundError')
except FileNotFoundError as e:
    print('FileNotFoundError raised correctly')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("FileNotFoundError raised correctly", output_str)
        self.assertNotIn("ERROR", output_str)
    
    def test_os_path_isfile(self):
        """Test os.path.isfile()"""
        code = """
import os.path
if os.path.isfile('test.txt'):
    print('test.txt is a file')
if not os.path.isfile('data/'):
    print('data/ is not a file')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("test.txt is a file", output_str)
    
    def test_os_path_isdir(self):
        """Test os.path.isdir()"""
        code = """
import os.path
if os.path.isdir('data/'):
    print('data/ is a directory')
if not os.path.isdir('test.txt'):
    print('test.txt is not a directory')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("data/ is a directory", output_str)
        self.assertIn("test.txt is not a directory", output_str)
    
    def test_file_size_bits_calculation(self):
        """Test calculating file size in bits (common use case)"""
        code = """
import os.path
size_bytes = os.path.getsize('test.txt')
size_bits = size_bytes * 8
print(f'Size: {size_bytes} bytes = {size_bits} bits')
if size_bits == 16:
    print('Found 16-bit file!')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("bytes", output_str)
        self.assertIn("bits", output_str)
    
    def test_delete_files_over_size(self):
        """Test deleting files over a certain size"""
        code = """
import os
import os.path

files = os.listdir()
for f in files:
    if os.path.isfile(f):
        size = os.path.getsize(f)
        if size * 8 > 16:  # More than 16 bits
            os.remove(f)
            print(f'Deleted: {f}')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        # test.txt should be deleted if it's over 16 bits
        # (depends on content, but likely will be)
    
    def test_iterate_file_lines(self):
        """Test iterating over file lines"""
        code = """
with open('test.txt', 'r') as f:
    for line in f:
        print(line.strip().upper())
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        self.assertGreaterEqual(len(self.output_lines), 3)
    
    def test_open_exclusive_mode(self):
        """Test open() with 'x' (exclusive) mode"""
        code = """
try:
    with open('newfile.txt', 'x') as f:
        f.write('New file\\n')
    print('File created successfully')
except FileExistsError:
    print('File already exists')
"""
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("File created successfully", output_str)
        
        # Try again - should fail
        self.output_lines = []
        success, error = self.executor.execute(
            code, self.filesystem, self.output_callback
        )
        self.assertTrue(success, f"Execution failed: {error}")
        output_str = " ".join(self.output_lines)
        self.assertIn("File already exists", output_str)


if __name__ == '__main__':
    unittest.main()
