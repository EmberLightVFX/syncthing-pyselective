from cx_Freeze import setup, Executable
  
setup(name = "syncthing-pyselective" ,
      version = "0.1" ,
      description = "" ,
      executables = [Executable("main.py")])