from semble_grammars import available_languages, get_language, get_parser

languages = available_languages()
assert languages, "no languages found in the installed wheel"

for lang in languages:
    get_language(lang)

tree = get_parser("python").parse(b"def f(): pass")
assert not tree.root_node.has_error, "python grammar failed to parse a trivial sample"
