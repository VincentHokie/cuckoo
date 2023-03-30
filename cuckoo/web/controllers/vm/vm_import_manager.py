from os import walk, path
import random
import shutil
import zipfile
import logging
from glob import glob
import calendar
import time
import threading

import subprocess
from IPy import IP

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

            vdi_files = [y for x in walk(unzip_vdi_location) for y in glob(path.join(x[0], '*.vdi'))]

            if len(vdi_files) != 1:
                self.db.update_vm_import_status(self.import_task.id, "No VDI File Found...")
                log.error("We must have one vdi file inside the zip file..")
                exit()

            vdi_file = vdi_files[0]
            _, filename = path.split(vdi_file)
            newvdiname = zip_vdi_location + "custom-" + filename
            shutil.move(vdi_file, newvdiname)

            self.db.update_vm_import_status(self.import_task.id, "Importing VM...")

            # (as dynamically as possible, find what IP address we can use for the VM being imported)
            network = "192.168.56.0/24"
            ip_addresses = IP(network)
            all_ip_addresses = [str(ip_address) for ip_address in ip_addresses]
            taken_ips = set()

            # get all the VMCloack VM IPs
            vmcloak_response = subprocess.check_output(["/home/ubuntu/venv/bin/vmcloak", "list", "vms"])
            # add the VMCloak IPs to the taken_ips
            taken_ips = set([new_split.split(" ")[1] for new_split in vmcloak_response.strip().split("\n")])

            # assuming only 1 exists
            dhcpservers_response = subprocess.check_output(["vboxmanage", "list", "dhcpservers"])
            dhcpservers_output = {new_split.split(":")[0]: new_split.split(":")[1].strip() for new_split in dhcpservers_response.strip().split("\n")}

            # add the dhcpserver IP to the taken IPs
            taken_ips.add(dhcpservers_output["IP"])
            # add the network, gateway, and broadcast addresses to the taken IPs
            taken_ips.update([all_ip_addresses[0], all_ip_addresses[1], all_ip_addresses[-1]])

            # remain with a list of available IPs
            available_ips = set(all_ip_addresses) - taken_ips

            if len(available_ips) == 0:
                self.db.update_vm_import_status(self.import_task.id, "No Available IP Addresses")
                raise Exception("No available IP addresses in the %s network." % network)

            cmd = ["/home/ubuntu/vmcloak.sh", str(int(ram) * 1024), str(osarch), str(osversion), str(vmname), str(cpu), str(newvdiname), str(random.choice(list(available_ips)))]
            log.debug("Running command: %s", cmd)
            subprocess.check_output(cmd)
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
            self.db.update_vm_import_status(self.import_task.id, "Errors encountered.")
            log.error("[-] Error importing a VM: %s", e)
        finally:
            task_log_stop(self.timestamp)