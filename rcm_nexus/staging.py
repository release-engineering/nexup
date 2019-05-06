import json
import time

from lxml import etree

STAGE_START_FORMAT = '/service/local/staging/profiles/{profile_id}/start'
STAGE_FINISH_FORMAT = '/service/local/staging/profiles/{profile_id}/finish'
STAGE_PROMOTE_FORMAT = '/service/local/staging/bulk/promote'
STAGE_REPO_FORMAT = "/service/local/staging/repository/{repo_id}"
STAGE_REPO_ACTIVITY_FORMAT = "/service/local/staging/repository/{repo_id}/activity"


def _get_staging_description(product, version, is_ga):
    return "%s, ver %s (to %s)" % (product, version, "GA" if is_ga else "Early-Access") 

def start_staging_repo(session, config, product, version, is_ga):
    profile_id = config.get_profile_id( product, is_ga )

    path = STAGE_START_FORMAT.format(profile_id=profile_id)
    request_data = etree.Element('promoteRequest')
    data = etree.SubElement( request_data, 'data')
    etree.SubElement(data, 'description').text=_get_staging_description(product, version, is_ga)

    xml = etree.tostring( request_data, xml_declaration=True, pretty_print=True, encoding='UTF-8')
    (response, text) = session.post(path, xml)

    # TODO: Error handling!

    repo_id = etree.fromstring(text).xpath('/promoteResponse/data/stagedRepositoryId/text()')
    return repo_id[0]

def finish_staging_repo(session, config, repo_id, product, version, is_ga):
    profile_id = config.get_profile_id( product, is_ga )

    path = STAGE_FINISH_FORMAT.format(profile_id=profile_id)
    request_data = etree.Element('promoteRequest')
    data = etree.SubElement( request_data, 'data')
    etree.SubElement(data, 'description').text=_get_staging_description(product, version, is_ga)
    etree.SubElement(data, 'stagedRepositoryId').text=repo_id

    xml = etree.tostring( request_data, xml_declaration=True, pretty_print=True, encoding='UTF-8')
    (response,text) = session.post(path, xml)

    # TODO: Error handling!
    # FIXME: Handle verification failure!


def promote(session, profile_id, repo_id, product, version, is_ga):
    path = STAGE_PROMOTE_FORMAT
    data = {
        "data": {
            "stagingProfileGroup": profile_id,
            "description": _get_staging_description(product, version, is_ga),
            "stagedRepositoryIds": [repo_id]
        }
    }

    response, text = session.post(
        path,
        json.dumps(data),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )


def verify_action(session, repo_id, action_name):
    """Go over activity on the given repository and report all errors.

    :returns: True if there was an error, False otherwise
    """
    has_errors = False
    path = STAGE_REPO_ACTIVITY_FORMAT.format(repo_id=repo_id)

    response, _ = session.get(path, headers={"Accept": "application/json"})
    response.raise_for_status()
    for action in response.json():
        if action["name"] == action_name:
            if "events" not in action:
                # No events yet, try downloading again
                time.sleep(3)
                return verify_action(session, repo_id, action_name)
            for event in action["events"]:
                if event["name"] == "ruleFailed":
                    for property in event["properties"]:
                        if property["name"] == "failureMessage":
                            print("Error: %s" % property["value"])
                            has_errors = True

    return has_errors
