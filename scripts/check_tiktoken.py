import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

text = "Hello, multi-tenant world! नमस्ते"
tokens = enc.encode(text)

print("chars :", len(text))
print("tokens:", len(tokens))
print("ids   :", tokens)
print("roundtrip ok:", enc.decode(tokens) == text)