# Copyright (C) 2013 Claudio Guarnieri.
# Copyright (C) 2014-2017 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

from django.conf.urls import url

from cuckoo.web.controllers.vm.routes import VirtualMachineRoutes

urlpatterns = [
    url(r"^api/info/$", VirtualMachineRoutes.tasks_info, name="vm/api/info"),
    url(r"^import/", VirtualMachineRoutes.import_, name="vm/import"),
]
