import logging
import os.path

from django.shortcuts import redirect

from cuckoo.core.database import Database
from cuckoo.core.submit import SubmitManager
from cuckoo.web.utils import view_error, render_template

from cuckoo.apps import cuckoo_machine
from cuckoo.web.controllers.vm.vmcloak_api import VMCloak
from cuckoo.core.startup import init_console_logging

import boto3
import zipfile

log = logging.getLogger(__name__)
submit_manager = SubmitManager()

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

        zip_vdi_location = "/tmp/"
        unzip_vdi_location = zip_vdi_location + vmname

        log.debug("Triggering zip file downlaod..")
        s3_client.download_file(vms_bucket, vmfile, zip_vdi_location + vmfile)
        log.debug("Completed zip file downlaod..")

        log.debug("Unzipping zip file..")
        with zipfile.ZipFile(zip_vdi_location + vmfile, 'r') as zip_ref:
            zip_ref.extractall(unzip_vdi_location)
        log.debug("Completed unzipping zip file..")

        import os
        from glob import glob
        import shutil
        vdi_files = [y for x in os.walk(unzip_vdi_location) for y in glob(os.path.join(x[0], '*.vdi'))]

        if len(vdi_files) != 1:
             log.error("We must have one vdi file inside the zip file..")
             exit()

        vdi_file = vdi_files[0]
        _, filename = os.path.split(vdi_file)
        newvdiname = zip_vdi_location + "custom-" + filename
        shutil.move(vdi_file, newvdiname)

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
