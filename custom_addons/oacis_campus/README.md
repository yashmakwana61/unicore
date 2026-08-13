Oacis Campus Management
=========================

Complete campus infrastructure management module for Oacis ERP.

Key Features
------------
- Multi-building campus management with floor-by-floor breakdown
- Room inventory with type classification and amenity tracking
- Facility management (sports, medical, canteen, etc.)
- Campus state workflow (Draft → Operational → Suspended → Closed)
- Smart dashboard with building/room/facility counts
- Printable campus infrastructure summary (QWeb PDF report)
- Full multi-company and multi-campus data isolation

Model Hierarchy
---------------
Campus → Building → Floor → Room
Campus → Facility

Security Groups Access
----------------------
- Administrator: Full CRUD on all models
- Manager: Read, write, create (no delete)
- Registrar: Read, write (no create, no delete)
- Staff: Read only
- Faculty: Read only
- Student: Read only

Dependencies
------------
- oacis_base: Base campus model, security groups, mixins
- oacis_security: Record rules, campus isolation, user campus assignment

Author: Precisefect Solutions Pvt. Ltd.
Website: https://precisefect.com
License: LGPL-3
