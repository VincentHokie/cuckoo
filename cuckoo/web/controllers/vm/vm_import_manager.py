from os import walk
import boto3
import shutil
import zipfile
import logging
from glob import glob
import calendar
import time
import threading
import Queue

from cuckoo.core.database import Database
from cuckoo.core.log import task_log_start, task_log_stop

log = logging.getLogger(__name__)

machinery = None
machine_lock = None
latest_symlink_lock = threading.Lock()


class VMImportManager(threading.Thread):
    """VM Import Manager.

    This class handles the full VM import process.
    """

    def __init__(self, s3_client, vms_bucket, db, import_task):
        """@param task: task object containing the details for the analysis."""
        threading.Thread.__init__(self)

        self.s3_client = s3_client
        self.vms_bucket = vms_bucket
        self.db = db
        self.import_task = import_task

        current_GMT = time.gmtime()
        self.timestamp = calendar.timegm(current_GMT)

        task_log_start(self.timestamp)

    def run(self):
        """Run manager thread."""
        try:

            ram = self.import_task.ram
            os = self.import_task.os
            osarch = self.import_task.os_arch
            osversion = self.import_task.os_version
            vmname = self.import_task.vm_name
            cpu = self.import_task.cpu
            vmfile = self.import_task.vm_file

            zip_vdi_location = "/tmp/"
            unzip_vdi_location = zip_vdi_location + vmname

            log.debug("Triggering zip file downlaod..")
            self.db.update_vm_import_status(self.import_task.id, "ZIP File Downloading...")
            self.s3_client.download_file(self.vms_bucket, vmfile, zip_vdi_location + vmfile)
            log.debug("Completed zip file downlaod..")

            log.debug("Unzipping zip file..")
            self.db.update_vm_import_status(self.import_task.id, "ZIP File Extraction...")
            with zipfile.ZipFile(zip_vdi_location + vmfile, 'r') as zip_ref:
                zip_ref.extractall(unzip_vdi_location)
            log.debug("Completed unzipping zip file..")

            vdi_files = [y for x in walk(unzip_vdi_location) for y in glob(os.path.join(x[0], '*.vdi'))]

            if len(vdi_files) != 1:
                self.db.update_vm_import_status(self.import_task.id, "No VDI File Found...")
                log.error("We must have one vdi file inside the zip file..")
                exit()

            vdi_file = vdi_files[0]
            _, filename = os.path.split(vdi_file)
            newvdiname = zip_vdi_location + "custom-" + filename
            shutil.move(vdi_file, newvdiname)

            self.db.update_vm_import_status(self.import_task.id, "Importing VM...")

            import subprocess
            cmd = ["/home/ubuntu/vmcloak.sh", str(int(ram) * 1024), osarch, osversion, vmname, cpu, newvdiname]
            log.debug("Running command: %s", cmd)
            ret = subprocess.check_output(cmd)
            self.db.update_vm_import_status(self.import_task.id, "VM Import Complete!")                        

            log.debug("VM Import process complete!")
            # Ideally, the above script should be a series of steps that can be tracked
            #
            # vmcloack = VMCloak()
            # vmcloack.init(os=os, os_version=osversion, arch=osarch, custom_name=vmname, cpu_count=cpu, ram_size=int(ram) * 1024, vdi_file=newvdiname)
            # vmcloack.clone(custom_name=vmname)
            # vmcloack.install(custom_name=vmname)
            # vmcloack.snapshot(custom_name=vmname)
        except Exception as e:
            log.error("[-] Error importing a VM: %s", e)
        finally:
            task_log_stop(self.timestamp)


class VMImportScheduler(object):
    """Tasks Scheduler.

    This class is responsible for the main execution loop of the import tool. It
    keeps waiting and loading for new import tasks as they come in.
    Whenever a new import task is available, it launches VMImportManager which will
    take care of running the full import process.
    """
    def __init__(self, maxcount=None):
        self.running = True
        self.db = Database()
        self.maxcount = maxcount
        self.import_managers = set()

    def stop(self):
        """Stop scheduler."""
        self.running = False

        # Force stop all analysis managers.
        for am in self.import_managers:
            try:
                am.force_stop()
            except Exception as e:
                log.exception("Error force stopping import manager: %s", e)

        # Remove network rules if any are present and stop auxiliary modules
        for am in self.import_managers:
            try:
                am.cleanup()
            except Exception as e:
                log.exception(
                    "Error while cleaning up import manager: %s", e
                )

    def _cleanup_managers(self):
        cleaned = set()
        for am in self.import_managers:
            if not am.isAlive():
                try:
                    am.cleanup()
                except Exception as e:
                    log.exception("Error in import manager cleanup: %s", e)

                cleaned.add(am)
        return cleaned

    def start(self):
        """Start scheduler."""

        log.info("Waiting for import tasks.")

        # Message queue with threads to transmit exceptions (used as IPC).
        errors = Queue.Queue()

        vms_bucket = "final-project-cuckoo-vms"
        s3_client = boto3.client("s3")

        # This loop runs forever.
        while self.running:
            time.sleep(1)

            # Run cleanup on finished import managers and untrack them
            for am in self._cleanup_managers():
                self.import_managers.discard(am)
            
            import_task = self.db.get_import_task_to_process()

            if import_task:
                log.debug("Processing import task #%s", import_task.id)

                # Initialize and start the import manager.
                import_manager = VMImportManager(s3_client, vms_bucket, self.db, import_task)
                import_manager.daemon = True
                import_manager.start()
                self.import_managers.add(import_manager)

            # Deal with errors.
            try:
                raise errors.get(block=False)
            except Queue.Empty:
                pass

        log.debug("End of import analyses.")
