def get_capsule_latest_release(client, capsule_id):
    original_capsule = client.capsules.get_capsule(capsule_id=capsule_id)
    release_capsule = client.capsules.get_capsule(
        capsule_id=original_capsule.release_capsule
    )
    latest_version = release_capsule.versions[-1]
    return latest_version


def capsule_git_url(capsule_slug):
    return f"https://poc-nci.codeocean.io/{capsule_slug}.git"
