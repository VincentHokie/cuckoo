from os import walk
import boto3
import shutil
import zipfile
import logging
from glob import glob
import calendar
import time
import threading

log = logging.getLogger(__name__)

machinery = None
machine_lock = None
latest_symlink_lock = threading.Lock()

active_analysis_count = 0


class VMImportManager(threading.Thread):
    """VM Import Manager.

    This class handles the full VM import process.
    """

    def __init__(self, s3_client, vms_bucket, db, request):
        """@param task: task object containing the details for the analysis."""
        threading.Thread.__init__(self)

        self.s3_client = s3_client
        self.vms_bucket = vms_bucket
        self.db = db
        self.request = request

    def run(self):
        """Run manager thread."""

        ram = self.request.POST['ram']
        os = self.request.POST['os']
        osarch = self.request.POST['osarch']
        osversion = self.request.POST['osversion']
        vmname = self.request.POST['vmname']
        cpu = self.request.POST['cpu']
        vmfile = self.request.POST['vmfile']

        current_GMT = time.gmtime()
        timestamp = calendar.timegm(current_GMT)

        vm_import_id = self.db.add_vm_import(
            vm_name = str(vmname), vm_file = str(vmfile), os = str(os),
            os_version = str(osversion), os_arch = str(osarch), cpu = int(cpu),
            ram = int(ram), file_log = "%s-%s-%s-%s" % (str(vmfile), str(os), str(osarch), str(timestamp))
        )

        zip_vdi_location = "/tmp/"
        unzip_vdi_location = zip_vdi_location + vmname

        log.debug("Triggering zip file downlaod..")
        self.db.update_vm_import_status(vm_import_id, "ZIP File Downloading...")
        self.s3_client.download_file(self.vms_bucket, vmfile, zip_vdi_location + vmfile)
        log.debug("Completed zip file downlaod..")

        log.debug("Unzipping zip file..")
        self.db.update_vm_import_status(vm_import_id, "ZIP File Extraction...")
        with zipfile.ZipFile(zip_vdi_location + vmfile, 'r') as zip_ref:
            zip_ref.extractall(unzip_vdi_location)
        log.debug("Completed unzipping zip file..")

        vdi_files = [y for x in walk(unzip_vdi_location) for y in glob(os.path.join(x[0], '*.vdi'))]

        if len(vdi_files) != 1:
            self.db.update_vm_import_status(vm_import_id, "No VDI File Found...")
            log.error("We must have one vdi file inside the zip file..")
            exit()

        vdi_file = vdi_files[0]
        _, filename = os.path.split(vdi_file)
        newvdiname = zip_vdi_location + "custom-" + filename
        shutil.move(vdi_file, newvdiname)

        self.db.update_vm_import_status(vm_import_id, "Importing VM...")

        try:
            import subprocess
            cmd = ["/home/ubuntu/vmcloak.sh", str(int(ram) * 1024), osarch, osversion, vmname, cpu, newvdiname]
            log.debug("Running command: %s", cmd)
            ret = subprocess.check_output(cmd)
            self.db.update_vm_import_status(vm_import_id, "VM Import Complete!")
        except Exception as e:
            log.error("[-] Error running command: %s", e)
            raise Exception
          
        log.debug("VM Import process complete!")
        # Ideally, the above script should be a series of steps that can be tracked
        #
        # vmcloack = VMCloak()
        # vmcloack.init(os=os, os_version=osversion, arch=osarch, custom_name=vmname, cpu_count=cpu, ram_size=int(ram) * 1024, vdi_file=newvdiname)
        # vmcloack.clone(custom_name=vmname)
        # vmcloack.install(custom_name=vmname)
        # vmcloack.snapshot(custom_name=vmname)
