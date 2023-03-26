import boto3
import logging

from django.shortcuts import redirect

from cuckoo.core.database import Database
from cuckoo.web.utils import view_error, render_template

from cuckoo.web.controllers.vm.vm_import_manager import VMImportManager
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
            return view_error(request, "Import VM request must be POST!")

        init_console_logging(level=logging.DEBUG)

        import_manager = VMImportManager(s3_client, vms_bucket, db, request)
        import_manager.daemon = True
        import_manager.start()

        return redirect("vm/success")
