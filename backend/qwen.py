from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import re
import scheduler
import json
import os
from datetime import datetime, timedelta

def launch():
    global model_path
    model_path = "/storage/ice-shared/vip-vp4/Fall2025/gptoss/hub/models--openai--gpt-oss-20b/snapshots/6cee5e81ee83917806bbde320786a8fb61efebee"
    sched_path = "scheduler.py"
    ics_path = "working.ics"
    print(ics_path)
    global sched_code
    global ics_content
    with open(sched_path, "r") as file:
        sched_code = file.read()
    with open(ics_path, "r") as file:
        ics_content = file.read()
    global model
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only = True,
        device_map="auto"
    )
    global tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_path)
def chat(prompt, ics_content):
    today = datetime.now().date()

    # build list of tuples for next 7 days
    week_list = [
        f"{(today + timedelta(days=i)).strftime('%A, %B %d, %Y')} ({(today + timedelta(days=i)).isoformat()})"
        for i in range(7)
    ]

    messages = [
        {"role": "system", "content": "You are an agentic scheduling assistant. Here is the codebase: %s. Output only the function call. Ensure that prefer_hours is a tuple. Include function name in call, not just the parameters. Do not enclose the function call with the word python or any quotation marks. The current time is %s. Schedule the event relative to this date with given timezones. The next week is: %s. The current working schedule is %s" % (sched_code, datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), str(week_list), ics_content)},
        {"role": "user", "content": prompt}
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    stop_ids = [tokenizer.eos_token_id]
    if "<|im_end|>" in tokenizer.get_vocab():
        stop_ids.append(tokenizer.convert_tokens_to_ids("<|im_end|>"))

    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=1300,
        eos_token_id=stop_ids
    )
    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]

    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    print("Response" +  response) 
    #answer = re.split(r'(\'\'\'|\"\"\")', text)[1].strip()
    #print("Answer" +  answer)
        
    response = response.split('assistantfinal')[1].strip()
    response = response.replace("python", "").strip("`")
    print("Function call: " + response)
    return response
#launch()
#output = chat("Add an event for lunch tomorrow.")
#print(output)
def call_sched(prompt):
    function_call_string = "scheduler." + prompt
    prompt = function_call_string
    function_name_end = function_call_string.find('(')
    function_name = function_call_string[:function_name_end]
    arguments_string = function_call_string[function_name_end + 1:-1]
    arguments = [arg.strip() for arg in arguments_string.split(',')]
    print(function_name)
    print(*arguments)
    print(function_call_string)
    if function_name == "scheduler.delete_event":
        eval(function_call_string)
        prompt = "Event successfully deleted"
    elif function_name == "scheduler.edit_event":
        eval(function_call_string)
        prompt = "Event successfully edited"
    elif function_name == "scheduler.find_optimal_slot":
        print("Adding event")
        prompt = eval(function_call_string)
        print(prompt)
    elif function_name == "scheduler.chat":
        prompt = scheduler.chat(prompt)
    else:
        raise ValueError("Function call could not be parsed")
        
    #print(prompt)
   # for key in prompt:
    #    prompt[key] = eval(prompt[key])
    print(prompt)
    return prompt
#print(call_sched(output))

            
