import logging
import os
import subprocess
import time

log = logging.getLogger(__name__)

class CommandError(Exception):
    pass


class VMCloak():

    def __init__(self, *args, **kwargs):
        self.vmcloak = "/home/ubuntu/venv/bin/vmcloak"

    def _call(self, *args, **kwargs):
        cmd = [self.vmcloak] + list(args)

        for k, v in kwargs.items():
            if v is None or v is True:
                cmd += ["--" + k]
            else:
                cmd += ["--" + k.rstrip("_"), str(v)]

        try:
            log.debug("Running command: %s", cmd)
            ret = subprocess.check_output(cmd)
        except Exception as e:
            log.error("[-] Error running command: %s", e)
            raise CommandError

        return ret.strip()

    def init(self, os, os_version, arch, custom_name, cpu_count, ram_size, vdi_file):
        osarch = ""
        if os == "windows":
            osarch = "--win" + str(os_version) + "x" + str(arch)

        return self._call(
            "init", osarch, custom_name, cpus=cpu_count, ramsize=ram_size, vdifile=vdi_file
        )

    def clone(self, custom_name):
        return self._call("clone", custom_name, "custom-" + custom_name)

    def install(self, custom_name):
        return self._call(
            "install", "custom-" + custom_name,
            "adobepdf", "pillow", "dotnet", "java", "flash", "vcredist", "vcredist.version=2015u3", "wallpaper", "ie11"
        )

    def snapshot(self, custom_name):
        return self._call("snapshot", "custom-" + custom_name, custom_name, "192.168.56.200", count=1)  
