import re

def test_regex():
    # Case 1: Plain XML
    c1 = """<tool_call>
<function=test>
</function>
</tool_call>"""
    
    # Case 2: Markdown Code Block
    c2 = """```xml
<tool_call>
<function=test>
</function>
</tool_call>
```"""

    # Case 3: Markdown Code Block with extra newlines
    c3 = """Here is the embed:
```xml
<tool_call>
<function=test>
</function>
</tool_call>
```
"""

    pattern = r'<tool_call>(.*?)</tool_call>'
    
    print("--- Case 1 (Plain) ---")
    m1 = re.findall(pattern, c1, re.DOTALL)
    print(f"Match: {bool(m1)}")
    
    print("--- Case 2 (Markdown) ---")
    m2 = re.findall(pattern, c2, re.DOTALL)
    print(f"Match: {bool(m2)}")
    
    print("--- Case 3 (Markdown + Text) ---")
    m3 = re.findall(pattern, c3, re.DOTALL)
    print(f"Match: {bool(m3)}")

if __name__ == "__main__":
    test_regex()
