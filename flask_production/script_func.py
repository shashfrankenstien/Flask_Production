import os, sys
import subprocess
from types import ModuleType


class ScriptFunc(ModuleType):

    def __init__(self, script_dir_path: str, script_name: str, *args) -> None:
        script_dir_path = os.path.abspath(script_dir_path)
        if not os.path.isdir(script_dir_path):
            raise ValueError(f"'{script_dir_path}' not found")

        if not script_name.endswith(".py"):
            raise ValueError("Only python scripts supported at this time")

        self.__file__ = os.path.join(script_dir_path, script_name)

        if not os.path.isfile(self.__file__):
            raise FileNotFoundError(f"'{self.__file__}' not found")

        self.__module__ = script_dir_path
        self.__qualname__ = f'[{script_name}]'
        if args:
            self.__qualname__ += ' ' + ' '.join(args)

        self.__doc__ = f"Script called '{script_name}' defined in '{script_dir_path}'"

        self.script_dir_path = script_dir_path
        self.script_name = script_name
        self.args = args





    def __call__(self):
        wd = os.getcwd()
        os.chdir(self.script_dir_path)
        cmd = [sys.executable, "-u", self.__file__] + list(self.args)

        try:
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

        finally:
            os.chdir(wd)

