import boto3
import logging
import calendar
import time

from django.shortcuts import redirect

from cuckoo.core.database import Database
from cuckoo.web.utils import view_error, render_template

from cuckoo.core.startup import init_console_logging

log = logging.getLogger(__name__)
db = Database()

class VirtualMachineRoutes(object):


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
            return view_error(request, "Import VM request must be POST!")

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

        db.add_vm_import(
            vm_name = str(vmname), vm_file = str(vmfile), os = str(os),
            os_version = str(osversion), os_arch = str(osarch), cpu = int(cpu),
            ram = int(ram), file_log = "%s-%s-%s-%s" % (str(vmfile), str(os), str(osarch), str(timestamp))
        )

        return redirect("vm/success")
