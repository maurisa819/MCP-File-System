# Use Cases for MCP File System

## UC 1: List Files

**Participating Actor:** initiated by User

**Entry Condition:** User is on the chat interface

**Exit Criteria:** A list of available files is displayed

**Flow of events:**

- User types “list files”
- Agent prompts user for confirmation
- User clicks Yes
- System retrieves file list from directory
- Agent displays files in the chat interface

## UC 2: Read File Contents

**Participating Actor:** initiated by User

**Entry Condition:** File exists in directory

**Exit Criteria:** File contents are displayed to the user

**Flow of events:**

- User requests to read a file
- Agent prompts for confirmation
- User clicks Yes
- System retrieves file content using file reader
- Agent displays the file contents

## UC 3: Create File

**Participating Actor:** initiated by User

**Entry Condition:** User is in chat interface

**Exit Criteria:** New file is created in the directory

**Flow of events:**

- User requests to create a file with content
- Agent prompts for confirmation
- User clicks Yes
- System creates file in directory
- Agent confirms file creation

## UC 4: Delete File

**Participating Actor:** initiated by User

**Entry Condition:** File exists in directory

**Exit Criteria:** File is removed from directory

**Flow of events:**

- User requests to delete a file
- Agent prompts for confirmation
- User clicks Yes
- System deletes file from directory
- Agent confirms deletion

## UC 6: Summarize File

**Participating Actor:** initiated by User

**Entry Condition:** File exists and is readable

**Exit Criteria:** Summary of file is displayed

**Flow of events:**

- User requests to summarize a file (for example: /summarize file_name)
- System retrieves file content
- LLM generates summary
- Agent displays summary

## UC 7: Summarize File and Save as New File

**Participating Actor:** initiated by User

**Entry Condition:** File exists

**Exit Criteria:** Summary file is created

**Flow of events:**

- User requests to summarize a file and save it (ex. /summarize file_name -> new_filename)
- System retrieves file content
- LLM generates summary
- System creates new file with summary
- Agent confirms file creation

## UC 8: Compare Two Files

**Participating Actor:** initiated by User

**Entry Condition:** At least two files exist and are readable

**Exit Criteria:** Comparison result is displayed to the user

**Flow of events:**

- User requests to compare two files (ex. /compare file1.docx and file2.docx)
- System retrieves both file contents
- Agent displays comparison results

## UC 9: Compare Two Files and Save as New file

**Participating Actor:** initiated by User

**Entry Condition:** At least two files exist and are readable

**Exit Criteria:** Comparison result is displayed to the user

**Flow of events:**

- User requests to compare two files (ex. /compare file1.docx and file2.docx -> compare.docx)
- System retrieves both file contents
- Agent confirms file creation

## UC 10: Get System Information

**Participating Actor:** initiated by User

**Entry Condition:** User is in chat interface

**Exit Criteria:** System information is displayed

**Flow of events:**

- User requests system information
- Agent prompts for confirmation
- User clicks Yes
- System retrieves OS details
- Agent displays system information

## UC 11: Confirm or Cancel Tool Execution

**Participating Actor:** initiated by User

**Entry Condition:** Agent proposes a tool action

**Exit Criteria:** Tool is executed or canceled

**Flow of events:**

- Agent asks for confirmation
- User selects Yes or No
- If Yes → tool executes
- If No → action is canceled
- Agent responds accordingly

## UC 12: Ask Questions About a File (Q&A)

**Participating Actor:** initiated by User

**Entry Condition:** File exists

**Exit Criteria:** Answer is generated based on file content

**Flow of events:**

- User asks a question about a file (ex. Based on file_name.pdf what is ...?)
- Agent prompts for confirmation
- User clicks Yes
- System retrieves file content
- LLM analyzes content
- Agent returns answer based on the file