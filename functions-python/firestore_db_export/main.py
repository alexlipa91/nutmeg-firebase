from googleapiclient.discovery import build


def firestore_db_export(request):
    request_json = request.get_json(silent=True)
    print("args {}, data {}".format(request.args, request_json))

    body = {
        'collectionIds': [],
        'outputUriPrefix': "gs://nutmeg-firestore-backup",
    }
    # Build REST API request for
    # https://cloud.google.com/firestore/docs/reference/rest/v1/projects.databases/exportDocuments
    project_id = "nutmeg-9099c"
    database_name = 'projects/{}/databases/(default)'.format(project_id)
    service = build('firestore', 'v1')
    service.projects().databases().exportDocuments(name=database_name, body=body).execute()
    return 'Operation started'
