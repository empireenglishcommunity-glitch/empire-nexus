import json, urllib.request

base_url = "http://localhost:3000/mcp"
auth = "Bearer EmpireMCP2026SecureToken"

def mcp_call(session_id, method, params, req_id):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Authorization": auth}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(base_url, data=data, headers=headers, method="POST")
    resp = urllib.request.urlopen(req)
    session = resp.headers.get("Mcp-Session-Id", session_id)
    raw = resp.read().decode()
    lines = raw.split('\n')
    for line in lines:
        if line.startswith("data:"):
            return session, json.loads(line[5:])
    return session, json.loads(raw)

print("Initializing MCP session...")
sid, r = mcp_call(None, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "fix", "version": "1.0"}}, 1)
print("Session:", sid)

new_code = """const c=$('Code Router').first().json;const cb=c.callback_data;const m=cb.match(/^q(\\\\d+)_(.+)$/);if(!m)return[{json:{chat_id:c.chat_id,text:'Error',reply_markup:'{}'}}];const qNum=parseInt(m[1]);const val=m[2];const Qs=[null,null,{t:'\\u2753 2/7\\n\\u062a\\u0642\\u062f\\u0631 \\u062a\\u0639\\u0631\\u0641 \\u0639\\u0646 \\u0646\\u0641\\u0633\\u0643 30 \\u062b\\u0627\\u0646\\u064a\\u0629\\u061f',o:[['\\u0644\\u0627','q2_0'],['\\u0628\\u0635\\u0639\\u0648\\u0628\\u0629','q2_1'],['\\u0646\\u0639\\u0645 \\u0645\\u0642\\u0628\\u0648\\u0644','q2_2'],['\\u0646\\u0639\\u0645 \\u0628\\u0633\\u0647\\u0648\\u0644\\u0629','q2_3']]},{t:'\\u2753 3/7\\n\\u0623\\u064a \\u062c\\u0645\\u0644\\u0629 \\u0635\\u062d\\u064a\\u062d\\u0629\\u061f',o:[['She go to work.','q3_0'],['She goes to work. \\u2705','q3_3'],['She going to work.','q3_1'],['She is go to work.','q3_0']]},{t:'\\u2753 4/7\\n\\u0645\\u0627\\u0630\\u0627 \\u062a\\u0639\\u0646\\u064a improve\\u061f',o:[['\\u064a\\u062a\\u062d\\u0633\\u0646 \\u2705','q4_3'],['\\u064a\\u062a\\u0648\\u0642\\u0641','q4_0'],['\\u064a\\u0633\\u0627\\u0641\\u0631','q4_0'],['\\u064a\\u0646\\u0633\\u0649','q4_0']]},{t:'\\u2753 5/7\\n\\u062a\\u0642\\u062f\\u0631 \\u062a\\u062a\\u0627\\u0628\\u0639 \\u0641\\u064a\\u062f\\u064a\\u0648 \\u0625\\u0646\\u062c\\u0644\\u064a\\u0632\\u064a \\u0628\\u0633\\u0631\\u0639\\u0629 \\u0637\\u0628\\u064a\\u0639\\u064a\\u0629\\u061f',o:[['\\u0644\\u0627 \\u0623\\u0641\\u0647\\u0645','q5_0'],['\\u0628\\u0639\\u0636 \\u0627\\u0644\\u0643\\u0644\\u0645\\u0627\\u062a','q5_1'],['\\u0645\\u0639\\u0638\\u0645\\u0647\\u0627','q5_2'],['\\u0643\\u0644 \\u0634\\u064a\\u0621','q5_3']]},{t:'\\u2753 6/7\\n\\u0645\\u0627 \\u0647\\u062f\\u0641\\u0643 \\u0627\\u0644\\u0623\\u0648\\u0644\\u061f',o:[['\\u0623\\u062a\\u0643\\u0644\\u0645 \\u0628\\u062b\\u0642\\u0629','q6_confidence'],['\\u0645\\u0642\\u0627\\u0628\\u0644\\u0629 \\u0639\\u0645\\u0644','q6_interview'],['\\u0627\\u0644\\u0633\\u0641\\u0631','q6_travel'],['\\u0627\\u062e\\u062a\\u0628\\u0627\\u0631','q6_exam'],['\\u062a\\u062d\\u0633\\u064a\\u0646 \\u0627\\u0644\\u0644\\u0647\\u062c\\u0629','q6_accent']]},{t:'\\u2753 7/7\\n\\u0643\\u0645 \\u0648\\u0642\\u062a \\u064a\\u0648\\u0645\\u064a\\u0627\\u061f',o:[['15 \\u062f\\u0642\\u064a\\u0642\\u0629','q7_Core'],['30 \\u062f\\u0642\\u064a\\u0642\\u0629','q7_Core'],['60+ \\u062f\\u0642\\u064a\\u0642\\u0629','q7_Intensive']]}];const next=qNum+1;if(next<=7&&Qs[next]){const q=Qs[next];const kb=JSON.stringify({inline_keyboard:q.o.map(x=>[{text:x[0],callback_data:x[1]}])});return[{json:{chat_id:c.chat_id,text:q.t,reply_markup:kb,_done:false,telegram_id:c.telegram_id,event_type:'QUIZ_ANSWER',timestamp:new Date().toISOString()}}];}const planText='\\u0646\\u062a\\u064a\\u062c\\u062a\\u0643: \\u0627\\u0644\\u0645\\u0633\\u062a\\u0648\\u0649 \\u0627\\u0644\\u0623\\u0648\\u0644 \\ud83d\\udcaa\\n\\n\\u0646\\u0631\\u0643\\u0632 \\u0639\\u0644\\u0649:\\n\\u2022 \\u0645\\u062d\\u0627\\u062f\\u062b\\u0627\\u062a \\u064a\\u0648\\u0645\\u064a\\u0629\\n\\u2022 \\u0627\\u0644\\u0625\\u064a\\u0642\\u0627\\u0639 \\u0627\\u0644\\u0623\\u0645\\u0631\\u064a\\u0643\\u064a\\n\\u2022 \\u062a\\u0648\\u0633\\u064a\\u0639 \\u0627\\u0644\\u0645\\u0641\\u0631\\u062f\\u0627\\u062a\\n\\n\\u062a\\u0628\\u064a \\u062a\\u0628\\u062f\\u0623\\u061f \\ud83d\\udc47';const kb2=JSON.stringify({inline_keyboard:[[{text:'\\ud83d\\udcc5 \\u0627\\u062d\\u062c\\u0632 \\u0645\\u0643\\u0627\\u0644\\u0645\\u0629',callback_data:'call'}],[{text:'\\ud83c\\udf81 \\u0647\\u062f\\u064a\\u062a\\u064a',callback_data:'resource'},{text:'\\u21a9\\ufe0f \\u0627\\u0644\\u0642\\u0627\\u0626\\u0645\\u0629',callback_data:'menu'}]]});return[{json:{chat_id:c.chat_id,text:planText,reply_markup:kb2,_done:true,telegram_id:c.telegram_id,first_name:c.first_name,event_type:'QUIZ_COMPLETED',timestamp:new Date().toISOString()}}];"""

print("Sending update...")
sid2, r2 = mcp_call(sid, "tools/call", {"name": "n8n_update_partial_workflow", "arguments": {"id": "lC9SVi4JDXZvAogr", "operations": [{"type": "updateNode", "name": "Quiz Answer Handler", "changes": {"parameters": {"jsCode": new_code}}}]}}, 2)
print(json.dumps(r2, indent=2))
