class BuiltinToolName:
    WEB_SEARCH = "web_search"

class ProviderBuiltInTool:
    OPENAI = {
        BuiltinToolName.WEB_SEARCH: {
            "type": "web_search"
        },
    }
    
    ANTHROPIC = {
        BuiltinToolName.WEB_SEARCH: {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5
        },
    }