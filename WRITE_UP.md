# Exploring Memory Strategies 

## Overview 

The goal is to explore different memory strategies. 
In the context of LLMs memory is the ability to persist information from one chat to another.

## Memory strategies

For all memory strategies the files were persisted to disk in JSON files. 

In future work it would be interesting to explore storing this data in a schema in a database,
and exploring things such as graph databaes to capture entity relationships.

### Fixed Vs Evolving

This explored the idea of utilizing a fixed hiearchy vs allowing the LLM to resolve the hierarchy. 
Prompts were used to express these contraints to the agent (refer to src/agent/prompts.py).

An evolving hierarcy allowed the LLM to discover new entities, and infer the relationships. This is
in contrast to the fixed hiearchy which enumerated the entities at the onset (company department, and person), and
a hiearchy overview prompt which outlined the file directory structure.

### Profile vs Episodic

The profile is based around the idea of creating summaries for the entries that get stored. 
For instance, if someone leaves the company the summary may indicate that the person formerly worked
at the company or the result will be updated to indicate that they no longer work there.

An episodic approach is effectively an append only log. Each update to the entity would be a new file.
Each update is time stamped and this allows the LLM to resolve a history of the entity.

## Approach

I crafted two harness stories. 
The first story is aligned with the fixed hierarchy in that it oultines a story about two coproations and their merger (scripts/seed_corp.sh) and (Read.md memory test scripts) for guidance on running the scripts.

The second story is only 3 statements about two children playing together, one getting injured, and the mom helping the children. 
This story is included, to better understand the impact of a fixed hiearchy. Although people are still the subject of the story they don't fit within a corporate hiearchy, and so the exploration is to see the impact of this.

For the sake of demonstrating that the memory is persisting the script creates a new chat instance for each message. All the chat instances are stored in a directory so once the script has been run once, you can point the chat to the directory and ask questions to evaluate the understanding of the LLM. 

The benefit of the directory structure is that you can also observe the directory structure easily to understand what the LLM has captured. 

### Limitations

It's strange that information is being reported to the chat. Specifically, the way the scripts were created is an agent is
being used to seed data, and then finally the agent is used to inquire about that data. This is confusing because the LLM
is taking on an agent persona when gathering data, and similarly when it's answering questions about data it may write updated
information about the entities.
Note that this construction makes sense for a typical business use case. It's not clear that a user will specifically want to upload data, and then ask about the data. It's more realistic that the user will do both at once. 

A related limitation is in the context of the test there wasn't an effective way to identify each user. In the scripts
the stories use their names, but there should probably be more prompting to handle name entity resolution, and recognition. 
What ends up happening with the LLM


## Embeddings

I didn't explore this extensively but in order to faciliate natural language search all these experiments were run with an ollama embedding model. In furhter explorations it'd be interesting to explore having the LLM resolve semantic similarity within its own model, and grepping for similar terms instead of having of relying on sematic search to power this.


## Results

### Corporation story


## Futher explorations / room for improvement



