import re
import json

def parse_xml(content):
    print(f"--- Parsing Content (len={len(content)}) ---")
    print(repr(content))
    
    # Copy of the cleanup logic
    content = content.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
    
    tool_calls = []
    pattern = r'<tool_call>(.*?)</tool_call>'
    matches = re.findall(pattern, content, re.DOTALL)
    
    print(f"Matches found: {len(matches)}")
    
    for match in matches:
        print(f"Match content: {repr(match)}")
        try:
            func_name = None
            func_patterns = [
                r'<function>([^<]+)</function>',
                r'<function-name>([^<]+)</function-name>', 
                r'<name>([^<]+)</name>',
                r'<function=([^>]+)>'
            ]
            
            for p in func_patterns:
                f_match = re.search(p, match)
                if f_match:
                    func_name = f_match.group(1).strip()
                    print(f"Found function name: {func_name} using pattern {p}")
                    break
            
            if not func_name:
                print("FAILED to find function name")
                continue
            
            params = {}
            param_pattern = r'<parameter=([^>]+)>'
            parts = re.split(param_pattern, match)
            
            if len(parts) > 1:
                for i in range(1, len(parts), 2):
                    p_name = parts[i].strip()
                    if i+1 < len(parts):
                         # Logic from current code: searching again in 'match'
                         # potential issue: what if multiple params have same name? (unlikely but possible)
                         p_block_pattern = f'<parameter={p_name}>(.*?)</parameter>'
                         p_val_match = re.search(p_block_pattern, match, re.DOTALL)
                         if p_val_match:
                             val = p_val_match.group(1).strip()
                             params[p_name] = val
                             print(f"  Param {p_name} = {val}")
            
            print(f"Final Params: {params}")
            
        except Exception as e:
            print(f"Error: {e}")

# Test Case 1: The user's specific failure
test_case_1 = """
<tool_call>
<function=send_embed>
<parameter=channel_id>1250573297502912522</parameter>
<parameter=title>Saludo</parameter>
<parameter=description>hola</parameter>
</function>
</tool_call> 
"""

parse_xml(test_case_1)
