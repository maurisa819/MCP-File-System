# Test/Use Cases

## General LLM interactions

### Use/Test Case 1

#### Functionality

Interact with the LLM without using the MCP server tools

#### Steps

1. Prompt LLM
2. there should be now prompt to grant/deny access to a tool

## MCP Server

### Use/Test Case 1

#### Functionality

Get a list of file the LLM has access to

### Steps

1. Prmopt LLM to get a list of file that it has access to
2. The LLM should process the user input
3. The Agent should prompt for access to use the List files MCP server tool
    1. If granted permission a list of file should be displayed
    2. if Denied nothing should be displayed.

### Use/Test Case 2

#### Functionality

Get the contents of a file

#### Steps

1. Prompt the LLM to get the contents of a file
2. LLM processes user input
3. The Agent should prompt for access to the MCP server tool
    1. if granted access the server should return the contents of the file
    2. if denied nothing should be returned

### Use/Test Case 3

#### Functionality

Get contents of the file from Use/Test Case 2 agin

#### Steps

1. Prompt the LLM to get the contents of the same file used in Test/Use Case 2
2. LLM should process the users input
3. Agent Actions
    1. If permission was granted in Test/Use Case 2 then no prompt should be displayed and the contents of the file should be returned
    2. If permission was denied in Test/Use Case 2 then the Agent should prompt for access to use the tool again

### Use/Test Case 4

#### Functionality

Getting the contents of multiple files

#### Steps

1. Prompt the LLM to getht econtents of multiple files
2. LLM will process the users input
3. Agent will prompt for access to the file
    1. If Granted access the contents will be retrieved
    2. If denied nothing will be returned
4. Step 3 is repeated for each file
