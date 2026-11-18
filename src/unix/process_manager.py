"""
Process management system for the virtual terminal
"""

import random


class Process:
    """Represents a running process"""

    def __init__(self, pid, command, cpu, mem, user="pilot", time_str="00:00.01"):
        self.pid = pid
        self.command = command
        self.cpu = cpu
        self.mem = mem
        self.user = user
        self.time_str = time_str
        self.is_system = False
        self.killable = True

    def __repr__(self):
        return f"Process(pid={self.pid}, command={self.command})"


class ProcessManager:
    """Manages virtual processes"""

    def __init__(self, save_system=None):
        self.processes = {}
        self.next_pid = 1000
        self.save_system = save_system
        # Check if virus has been killed from save system
        if save_system and save_system.is_virus_killed():
            self.virus_active = False
        else:
            self.virus_active = True
        self.virus_discovered = False

        # Initialize system processes
        self._init_system_processes()

    def _init_system_processes(self):
        """Initialize default system processes"""
        system_processes = [
            Process(1, "systemd", 0.0, 0.1, "root", "00:12.34"),
            Process(2, "kthreadd", 0.0, 0.0, "root", "00:00.00"),
            Process(100, "blthll_term", random.uniform(1.0, 3.0), random.uniform(2.0, 5.0), "pilot", "00:03.12"),
            Process(101, "shell", random.uniform(0.5, 1.5), random.uniform(1.0, 2.0), "pilot", "00:02.45"),
            Process(102, "fs_monitor", random.uniform(0.1, 0.5), random.uniform(0.5, 1.0), "pilot", "00:01.23"),
        ]

        for proc in system_processes:
            proc.is_system = True
            proc.killable = False
            self.processes[proc.pid] = proc

        # Add the hidden virus
        if self.virus_active:
            self._add_virus_process()

    def _add_virus_process(self):
        """Add the virus process with a disguised name"""
        # Virus disguises itself with a system-sounding name
        virus_names = [
            "systemd-logind",
            "kernel_task",
            "update_daemon",
            "system_monitor",
            "bg_service",
        ]
        virus_name = random.choice(virus_names)

        # Virus has suspiciously high CPU usage
        virus = Process(
            pid=random.randint(200, 500),
            command=virus_name,
            cpu=random.uniform(15.0, 35.0),  # High CPU usage!
            mem=random.uniform(5.0, 15.0),   # High memory usage!
            user="root",  # Running as root
            time_str=f"{random.randint(10, 99)}:{random.randint(10, 59)}.{random.randint(10, 99)}"
        )
        virus.is_system = False
        virus.killable = True
        virus.is_virus = True
        self.processes[virus.pid] = virus

    def add_process(self, command, cpu_usage=None, mem_usage=None):
        """
        Add a new user process

        Args:
            command: Command name
            cpu_usage: CPU usage percentage (random if None)
            mem_usage: Memory usage in MB (random if None)

        Returns:
            int: PID of new process
        """
        pid = self.next_pid
        self.next_pid += 1

        if cpu_usage is None:
            cpu_usage = random.uniform(0.5, 5.0)
        if mem_usage is None:
            mem_usage = random.uniform(1.0, 10.0)

        proc = Process(pid, command, cpu_usage, mem_usage, "pilot", "00:00.01")
        proc.is_system = False
        proc.killable = True
        self.processes[pid] = proc

        return pid

    def remove_process(self, pid):
        """
        Remove a process

        Args:
            pid: Process ID to remove

        Returns:
            tuple: (success, message, was_virus)
        """
        if pid not in self.processes:
            return (False, f"kill: ({pid}) - No such process", False)

        proc = self.processes[pid]

        # Check if it's the virus
        was_virus = hasattr(proc, 'is_virus') and proc.is_virus

        if not proc.killable:
            return (False, f"kill: ({pid}) - Operation not permitted (system process)", False)

        del self.processes[pid]

        if was_virus:
            self.virus_active = False
            return (True, f"Process {pid} ({proc.command}) terminated", True)

        return (True, f"Process {pid} ({proc.command}) terminated", False)

    def get_processes(self):
        """Get list of all processes sorted by CPU usage"""
        processes = list(self.processes.values())

        # Filter out virus processes if virus has been killed
        if self.save_system and self.save_system.is_virus_killed():
            # Remove any processes that are marked as the virus
            processes = [p for p in processes if not (hasattr(p, 'is_virus') and p.is_virus)]

        return sorted(processes, key=lambda p: p.cpu, reverse=True)

    def get_process(self, pid):
        """Get a specific process by PID"""
        return self.processes.get(pid)

    def update_cpu_usage(self):
        """Randomly update CPU usage to simulate activity"""
        for proc in self.processes.values():
            if hasattr(proc, 'is_virus') and proc.is_virus:
                # Virus keeps high CPU
                proc.cpu = random.uniform(15.0, 35.0)
            elif proc.is_system:
                # System processes have low, stable CPU
                proc.cpu = random.uniform(0.0, 2.0)
            else:
                # User processes vary
                proc.cpu = random.uniform(0.1, 5.0)

    def mark_virus_discovered(self):
        """Mark that the player has discovered the virus"""
        self.virus_discovered = True


