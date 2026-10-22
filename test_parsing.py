from backend.llm_utils import parse_llm_response
import json

def test_parsing():
    print("Testing Parse Logic...")
    
    # Case 1: Perfect JSON with Title and Tool
    raw_1 = """
    ```json
    {
      "chat_title": "Beam Check",
      "content": "Here is the calculation.",
      "tool": {
        "tool_name": "generate_calculator_tool",
        "arguments": {
          "tool_name": "Beam Calc",
          "description": "Calculate beam",
          "inputs": []
        }
      }
    }
    ```
    """
    c, t, title = parse_llm_response(raw_1)
    assert title == "Beam Check"
    assert "Here is the calculation" in c
    assert t.tool_name == "Beam Calc"
    print("Case 1 Passed")

    # Case 2: No Code Blocks, Just JSON
    raw_2 = """
    {
      "chat_title": "Simple Chat",
      "content": "Just talking.",
      "tool": null
    }
    """
    c, t, title = parse_llm_response(raw_2)
    assert title == "Simple Chat"
    assert t is None
    print("Case 2 Passed")

    # Case 3: Error / Text fallback (Simulated by invalid JSON)
    raw_3 = "This is just text without JSON."
    c, t, title = parse_llm_response(raw_3)
    # The current logic might return the whole text as content if regex fails
    # My regex expects { }, so if no curly braces, it might return None or original.
    # Let's check implementation: 
    # if not json_match (which needs { }), it falls to `return response_text, None, None` exception block?
    # No, it returns `response_text, None, None` if execution hits exception or loop end.
    assert c == raw_3
    print("Case 3 Passed")

if __name__ == "__main__":
    test_parsing()
