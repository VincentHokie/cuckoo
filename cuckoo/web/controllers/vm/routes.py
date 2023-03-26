import os
import boto3
import shutil
import zipfile
import logging
from glob import glob
import calendar
import time

from django.shortcuts import redirect

from cuckoo.core.database import Database
from cuckoo.web.utils import view_error, render_template

from cuckoo.web.controllers.vm.vmcloak_api import VMCloak
from cuckoo.core.startup import init_console_logging

log = logging.getLogger(__name__)
db = Database()

class VirtualMachineRoutes(object):

    @staticmethod
    def success(request):
        return render_template(request, "vm/success.html")
    
    @staticmethod
    def error(request):
        return render_template(request, "vm/error.html")

    @staticmethod
    def import_(request):
        # boto3.setup_default_session(profile_name='personal')
        vms_bucket = "final-project-cuckoo-vms"
        s3_client = boto3.client("s3")

        if request.method == "GET":
            response = s3_client.list_objects_v2(Bucket=vms_bucket)
            files = response.get("Contents")

            available_vms = [file['Key'] for file in files]

            return render_template(request, "vm/import.html", available_vms=available_vms)

        if request.method != "POST":
            return view_error(request, "Import analysis request must be POST!")

        init_console_logging(level=logging.DEBUG)

        ram = request.POST['ram']
        os = request.POST['os']
        osarch = request.POST['osarch']
        osversion = request.POST['osversion']
        vmname = request.POST['vmname']
        cpu = request.POST['cpu']
        vmfile = request.POST['vmfile']

        current_GMT = time.gmtime()
        timestamp = calendar.timegm(current_GMT)

        vm_import_id = db.add_vm_import(
            vm_name = str(vmname), vm_file = str(vmfile), os = str(os),
            os_version = str(osversion), os_arch = str(osarch), cpu = int(cpu),
            ram = int(ram), file_log = "%s-%s-%s-%s" % (str(vmfile), str(os), str(osarch), str(timestamp))
        )

        zip_vdi_location = "/tmp/"
        unzip_vdi_location = zip_vdi_location + vmname

        log.debug("Triggering zip file downlaod..")
        db.update_vm_import_status(vm_import_id, "ZIP File Downloading...")
        s3_client.download_file(vms_bucket, vmfile, zip_vdi_location + vmfile)
        log.debug("Completed zip file downlaod..")

        log.debug("Unzipping zip file..")
        db.update_vm_import_status(vm_import_id, "ZIP File Extraction...")
        with zipfile.ZipFile(zip_vdi_location + vmfile, 'r') as zip_ref:
            zip_ref.extractall(unzip_vdi_location)
        log.debug("Completed unzipping zip file..")

        vdi_files = [y for x in os.walk(unzip_vdi_location) for y in glob(os.path.join(x[0], '*.vdi'))]

        if len(vdi_files) != 1:
            db.update_vm_import_status(vm_import_id, "No VDI File Found...")
            log.error("We must have one vdi file inside the zip file..")
            exit()

        vdi_file = vdi_files[0]
        _, filename = os.path.split(vdi_file)
        newvdiname = zip_vdi_location + "custom-" + filename
        shutil.move(vdi_file, newvdiname)

        db.update_vm_import_status(vm_import_id, "Importing VM...")

        try:
            import subprocess
            cmd = ["/home/ubuntu/vmcloak.sh", str(int(ram) * 1024), osarch, osversion, vmname, cpu, newvdiname]
            log.debug("Running command: %s", cmd)
            ret = subprocess.check_output(cmd)
        except Exception as e:
            log.error("[-] Error running command: %s", e)
            raise Exception

        # Ideally, the above script should be a series of steps that can be tracked
        #
        # vmcloack = VMCloak()
        # vmcloack.init(os=os, os_version=osversion, arch=osarch, custom_name=vmname, cpu_count=cpu, ram_size=int(ram) * 1024, vdi_file=newvdiname)
        # vmcloack.clone(custom_name=vmname)
        # vmcloack.install(custom_name=vmname)
        # vmcloack.snapshot(custom_name=vmname)

        return redirect("vm/success")
