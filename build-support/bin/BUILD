python_sources(
    name="sources",
    sources=["**/*.py"],
)

pex_binary(
    name="ol-project",
    entry_point="mitol.build_support.cli:cli",
    dependencies=[
        ":sources",
    ],
)
