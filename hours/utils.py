def get_resource_pk_filter(pk):
    if ":" not in pk:
        return {"pk": pk}

    # Find the object using resource origin
    data_source_id, origin_id = pk.split(":")
    return {
        "resourceorigin__data_source_id": data_source_id,
        "resourceorigin__origin_id": origin_id,
    }
