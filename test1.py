"""
STORM Wiki pipeline powered by GPT-3.5/4 and You.com search engine.
You need to set up the following environment variables to run this script:
    - OPENAI_API_KEY: OpenAI API key
    - OPENAI_API_TYPE: OpenAI API type (e.g., 'openai' or 'azure')
    - AZURE_API_BASE: Azure API base URL if using Azure API
    - AZURE_API_VERSION: Azure API version if using Azure API
    - YDC_API_KEY: You.com API key; or, BING_SEARCH_API_KEY: Bing Search API key

Output will be structured as below
args.output_dir/
    topic_name/  # topic_name will follow convention of underscore-connected topic name w/o space and slash
        conversation_log.json           # Log of information-seeking conversation
        raw_search_results.json         # Raw search results from search engine
        direct_gen_outline.txt          # Outline directly generated with LLM's parametric knowledge
        storm_gen_outline.txt           # Outline refined with collected information
        url_to_info.json                # Sources that are used in the final article
        storm_gen_article.txt           # Final article generated
        storm_gen_article_polished.txt  # Polished final article (if args.do_polish_article is True)
"""

import os
from argparse import ArgumentParser

from knowledge_storm import STORMWikiRunnerArguments, STORMWikiRunner, STORMWikiLMConfigs
from knowledge_storm.lm import OpenAIModel, AzureOpenAIModel
from knowledge_storm.rm import YouRM, BingSearch, BraveRM
from knowledge_storm.utils import load_api_key


def main(args):
    load_api_key(toml_file_path='secrets.toml')
    lm_configs = STORMWikiLMConfigs()
    openai_kwargs = {
        'api_key': os.getenv("OPENAI_API_KEY"),
        'temperature': 1.0,
        'top_p': 0.9,
    }

    ModelClass = OpenAIModel if os.getenv('OPENAI_API_TYPE') == 'openai' else AzureOpenAIModel
    gpt_35_model_name = 'gpt-3.5-turbo' if os.getenv('OPENAI_API_TYPE') == 'openai' else 'gpt-35-turbo'
    gpt_4_model_name = 'gpt-4o'
    if os.getenv('OPENAI_API_TYPE') == 'azure':
        openai_kwargs['api_base'] = os.getenv('AZURE_API_BASE')
        openai_kwargs['api_version'] = os.getenv('AZURE_API_VERSION')

    conv_simulator_lm = ModelClass(model=gpt_35_model_name, max_tokens=500, **openai_kwargs)
    question_asker_lm = ModelClass(model=gpt_35_model_name, max_tokens=500, **openai_kwargs)
    outline_gen_lm = ModelClass(model=gpt_4_model_name, max_tokens=400, **openai_kwargs)
    article_gen_lm = ModelClass(model=gpt_4_model_name, max_tokens=700, **openai_kwargs)
    article_polish_lm = ModelClass(model=gpt_4_model_name, max_tokens=4000, **openai_kwargs)

    lm_configs.set_conv_simulator_lm(conv_simulator_lm)
    lm_configs.set_question_asker_lm(question_asker_lm)
    lm_configs.set_outline_gen_lm(outline_gen_lm)
    lm_configs.set_article_gen_lm(article_gen_lm)
    lm_configs.set_article_polish_lm(article_polish_lm)

    engine_args = STORMWikiRunnerArguments(
        output_dir=args.output_dir,
        max_conv_turn=args.max_conv_turn,
        max_perspective=args.max_perspective,
        search_top_k=args.search_top_k,
        max_thread_num=args.max_thread_num,
    )

    if args.retriever == 'bing':
        rm = BingSearch(bing_search_api=os.getenv('BING_SEARCH_API_KEY'), k=engine_args.search_top_k)
    elif args.retriever == 'you':
        rm = YouRM(ydc_api_key=os.getenv('YDC_API_KEY'), k=engine_args.search_top_k)
    elif args.retriever == 'brave':
        rm = BraveRM(brave_search_api_key=os.getenv('BRAVE_API_KEY'), k=engine_args.search_top_k)

    runner = STORMWikiRunner(engine_args, lm_configs, rm)

    # Directly set the topic here
    topic = "AI and its Effect on Science"
    runner.run(
        topic=topic,
        do_research=args.do_research,
        do_generate_outline=args.do_generate_outline,
        do_generate_article=args.do_generate_article,
        do_polish_article=args.do_polish_article,
    )
    runner.post_run()
    runner.summary()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--output-dir', type=str, default='./results/gpt',
                        help='Directory to store the outputs.')
    parser.add_argument('--max-thread-num', type=int, default=3,
                        help='Maximum number of threads to use.')
    parser.add_argument('--retriever', type=str, choices=['bing', 'you', 'brave'], default='you',
                        help='The search engine API to use for retrieving information.')
    parser.add_argument('--do-research', action='store_true', default=True,
                        help='Simulate conversation to research the topic.')
    parser.add_argument('--do-generate-outline', action='store_true', default=True,
                        help='Generate an outline for the topic.')
    parser.add_argument('--do-generate-article', action='store_true', default=True,
                        help='Generate an article for the topic.')
    parser.add_argument('--do-polish-article', action='store_true', default=True,
                        help='Polish the article by adding a summarization section and removing duplicate content.')
    parser.add_argument('--max-conv-turn', type=int, default=5,
                        help='Maximum number of questions in conversational question asking.')
    parser.add_argument('--max-perspective', type=int, default=5,
                        help='Maximum number of perspectives to consider in perspective-guided question asking.')
    parser.add_argument('--search-top-k', type=int, default=10,
                        help='Top k search results to consider for each search query.')
    parser.add_argument('--retrieve-top-k', type=int, default=3,
                        help='Top k collected references for each section title.')
    parser.add_argument('--remove-duplicate', action='store_true', default=True,
                        help='Remove duplicate content from the article.')

    main(parser.parse_args())
