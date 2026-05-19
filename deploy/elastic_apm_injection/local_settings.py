INSTALLED_APPS += [  # noqa: F821
    "elasticapm.contrib.django",
]

ELASTIC_APM = {
    "SERVER_TIMEOUT": "15s",
}
