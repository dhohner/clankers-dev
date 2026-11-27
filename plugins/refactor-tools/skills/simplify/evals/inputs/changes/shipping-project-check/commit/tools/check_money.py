"""Fails when code under shop/ uses float literals or float() calls, because money must use Decimal."""
import io
import pathlib
import sys
import tokenize

problems = []
for path in sorted(pathlib.Path("shop").rglob("*.py")):
    tokens = tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
    for token in tokens:
        is_float_literal = token.type == tokenize.NUMBER and any(c in token.string for c in ".eE")
        is_float_call = token.type == tokenize.NAME and token.string == "float"
        if is_float_literal or is_float_call:
            problems.append(f"{path}:{token.start[0]}: {token.string}")

print("\n".join(problems) or "check_money: ok")
sys.exit(1 if problems else 0)
