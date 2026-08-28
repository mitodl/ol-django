### Fixed

- Restored the distribution name to `mitol-django-digital-credentials`. It was
  changed to `mitol-django-digitalcredentials` during the Pants-to-Rye
  migration, and because PEP 503 normalization does not collapse that hyphen
  the two names are different PyPI projects. The renamed project was never
  created, so every release since 2023-12-19 failed silently while version tags
  continued to be pushed. Install the package as
  `mitol-django-digital-credentials`.
