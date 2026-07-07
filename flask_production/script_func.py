import os
import sys
import subprocess
import threading
from types import ModuleType
from typing import List


# ModuleType is used here only to provide module-like metadata
# (e.g. __module__ and __qualname__) for script jobs.
# This class does not behave as a real importable Python module.
class ScriptFunc(ModuleType):

    def __init__(self, script_dir_path: str, script_name: str, script_args: List[str]=None) -> None:
        script_dir_path = os.path.abspath(script_dir_path)
        script_args = script_args or []

        if not os.path.isdir(script_dir_path):
            raise ValueError(f"'{script_dir_path}' not found")

        if not script_name.endswith(".py"):
            raise ValueError("Only python scripts supported at this time")

        if not isinstance(script_args, list):
            raise TypeError('script_args should be a list')

        self.__file__ = os.path.join(script_dir_path, script_name)

        if not os.path.isfile(self.__file__):
            raise FileNotFoundError(f"'{self.__file__}' not found")

        self.script_dir_path = script_dir_path
        self.script_name = script_name
        self.script_args = list(str(s) for s in script_args)

        self.__module__ = self.script_dir_path
        self.__qualname__ = f'[{self.script_name}]'
        if len(self.script_args) > 0:
            self.__qualname__ += ' ' + ' '.join(self.script_args)

        self.__doc__ = f"Script called '{self.script_name}' defined in '{self.script_dir_path}'"

        self.__wd = os.getcwd() # capture working directory to change back to once script is complete


    def __call__(self):
        os.chdir(self.script_dir_path)
        cmd = [sys.executable, "-u", self.__file__] + self.script_args

        def _read_stream(stream, output_list):
            # Read lines as they arrive so stdout can be streamed live.
            for line in iter(stream.readline, ""):
                if not line:
                    break
                text = line.rstrip()
                print(text)
                output_list.append(text)

        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            stderr_lines = []
            stderr_thread = threading.Thread(
                target=_read_stream,
                args=(p.stderr, stderr_lines),
                daemon=True,
            )
            stderr_thread.start()

            # Stream stdout while the process is running.
            while p.poll() is None:
                line = p.stdout.readline()
                if line:
                    print(line.rstrip())

            # Wait for the process to finish, then drain any final stdout lines.
            # Using .read() here would block until the process exits and would lose the live stdout streaming behavior.
            p.wait()
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                print(line.rstrip())
            stderr_thread.join()

            # Keep stderr separate so failures can be raised from that stream only.
            err = "\n".join(stderr_lines).strip()
            if p.returncode != 0:
                if err:
                    e = err.split('\n')[-1]
                    raise Exception(f"{e}\n\nraised from subprocess:\n{err}")
                raise Exception(f"subprocess exited with code {p.returncode}")
            elif err:
                print(err)

        finally:
            os.chdir(self.__wd)

