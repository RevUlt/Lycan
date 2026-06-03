import re

def test_robust_regex():
    cases = [
        # Standard
        "<tool_call><function>test</function></tool_call>",
        # User style
        "<tool_call>\n<function=test>\n<parameter=a>1</parameter>\n</function>\n</tool_call>",
        # Spaced out
        "< tool_call >\n< function = test >\n</ tool_call >",
        # Mixed
        "```xml\n<tool_call>\n<function=test>\n</function>\n</tool_call>\n```"
    ]
    
    # Nuclear Regex for tool_call block
    block_pattern = r'<\s*tool_call\s*>(.*?)<\s*/\s*tool_call\s*>'
    
    print("--- Testing Block Capture ---")
    for i, c in enumerate(cases):
        m = re.search(block_pattern, c, re.DOTALL | re.IGNORECASE)
        print(f"Case {i}: {'MATCH' if m else 'FAIL'}")
        if m:
            block = m.group(1)
            # Nuclear Regex for function name
            # 1. <function>name</function>
            # 2. <function=name>
            # 3. <function-name>name</function>
            # 4. <name>name</name>
            
            func_name = None
            
            # Pattern A: Tag with value inside (function, function-name, name)
            p_tag = r'<\s*(function|function-name|name)\s*>([^<]+)<\s*/\s*(?:\1)\s*>'
            m_tag = re.search(p_tag, block, re.DOTALL | re.IGNORECASE)
            
            # Pattern B: Self-contained tag with attribute-like style <function=name>
            p_attr = r'<\s*function\s*=\s*([^>]+)\s*>'
            m_attr = re.search(p_attr, block, re.DOTALL | re.IGNORECASE)
            
            if m_tag:
                print(f"  -> Func (Tag): {m_tag.group(2).strip()}")
            elif m_attr:
                print(f"  -> Func (Attr): {m_attr.group(1).strip()}")
            else:
                 # Pattern C: Loose <function>NAME (no closing) - rare but possible
                 pass
                 print(f"  -> Func: FAIL in block: {repr(block)}")

if __name__ == "__main__":
    test_robust_regex()
