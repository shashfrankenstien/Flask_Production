import os, sys
import subprocess
from types import ModuleType


class ScriptFunc(ModuleType):

    def __init__(self, abs_dir_path, script_name, *args) -> None:
        self.abs_dir_path = abs_dir_path
        self.script_name = script_name
        self.args = args

        self.__module__ = abs_dir_path
        self.__qualname__ = f'[{script_name}]'
        self.__file__ = os.path.join(abs_dir_path, script_name)
        if args:
            self.__qualname__ += ' ' + ' '.join(args)
        self.__doc__ = f"Script called '{script_name}' defined in '{abs_dir_path}'"


    def __call__(self):
        cmd = [sys.executable, "-u", self.__file__] + list(self.args)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Grab stdout line by line as it becomes available.  This will loop until p terminates.
        while p.poll() is None:
            l = p.stdout.readline().decode().strip() # This blocks until it receives a newline.
            print(l)
        # # When the subprocess terminates there might be unconsumed output
        # # that still needs to be processed.
        print(p.stdout.read().decode().strip())
        err = p.stderr.read().decode().strip()
        if err:
            e = err.split('\n')[-1]
            raise Exception(f"{e}\n\nraised from subprocess:\n{err}")
        p.wait()

