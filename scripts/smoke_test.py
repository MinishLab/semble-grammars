from semble_grammars import available_languages, get_parser

languages = available_languages()
assert languages, "no languages found in the installed wheel"

tree = get_parser("python").parse(b"def f(): pass")
assert not tree.root_node.has_error, "python grammar failed to parse a trivial sample"

print(f"smoke test ok: {len(languages)} languages available")
