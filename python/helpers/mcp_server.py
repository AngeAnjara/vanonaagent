# fastmcp disabled for compatibility
def start_mcp_server():
    print("MCP server disabled (fastmcp removed).")

# fastmcp disabled for compatibility

class DynamicMcpProxy:
    @staticmethod
    def get_instance():
        print("MCP disabled")
        return None  # retourne None pour éviter le crash

