# vipr_django

- Alternate solutions for DellEMC ViPR-Controller
- Infrastructure operation automation with Python Django framework and custom ansible modules.

### Pre-Requirements
For running applications, following tools/apps are expected to install the server, which you'd deplpoy to this application.
- Tools
  - naviseccli
    - For executing `storops` python library.
  - ansible
    - For operating the storage-devices/FC-Switches with ansible-playbooks.
  - git
    - For version controlling of paremeter sheet `group_vars/all.yml`.
  - MongoDB
    - For storing data of each storage-devices

- Fingerprint registration between server ansible installed and each storage devices
- Permission of `controller/group_vars/all.yml` file, since user `apache` would modify it,


### REST-API
- Current URI patterns below:
  - `Catalog Histories`
    - CRUD Implementation with URI `/api/v1/cataloghist/`
      - `GET`,`POST`,`PUT`,`DELETE` with Django models
      - database name within SQLite3 is `controller_cataloghistory`

  - `Operations`
    - Only `POST` method is allowed to the interface `/api/v1/operations/`
      - Running Ansible playbook, POST with JSON request bodies.
    - Case if failed to kick ansible commands, API returns `{'result': 'Failed during ansible module executing...', 'stdout': data_result}`
      - variable `data_result` would be returned as ansible stdout in Shell.
    - Case else if some wrong data POSTed to API, it returns `{'result': 'Some wrong data provided. Check request-body.'}`
    - When you POSTed as expected, API returns `{'result': 'Success !!', 'stdout': data_result}`

  - `Device Searching`
    - Only `GET` method is allowed to the interface `/api/v1/search/`
