"""Opt-in search. Only the question is sent; no documents, history or memories."""
import asyncio,os,re
from datetime import datetime,timezone
import httpx

async def search(query):
    if os.getenv('YOUAI_SEARCH_PROVIDER','duckduckgo') == 'duckduckgo':
        try:
            items = await asyncio.wait_for(asyncio.to_thread(free_search, query), timeout=25)
        except Exception as error:
            raise ValueError('Free web search is temporarily unavailable or rate limited. Try again later.') from error
        return sources_from([{'url':item.get('href',''),'title':item.get('title',''),
                              'description':item.get('body','')} for item in items])
    if os.getenv('YOUAI_SEARCH_PROVIDER') != 'brave':
        raise ValueError('Unknown search provider. Use duckduckgo or brave.')
    key=os.getenv('YOUAI_BRAVE_KEY','')
    if not key:raise ValueError('Web search needs YOUAI_BRAVE_KEY on the laptop. Set it and restart YouAI. Your question has not been sent anywhere.')
    async with httpx.AsyncClient(timeout=20,trust_env=False) as client:
        response=await client.get('https://api.search.brave.com/res/v1/web/search',params={'q':query,'count':5},headers={'X-Subscription-Token':key,'Accept':'application/json'})
        if response.status_code in (401,403):
            raise ValueError('Brave rejected the search key. Check your API subscription and YOUAI_BRAVE_KEY.')
        if response.status_code == 429:
            raise ValueError('Web search quota reached. Try again later or check your Brave plan.')
        if response.is_error:
            raise ValueError('Web search provider is unavailable. Try again later.')
    return sources_from(response.json().get('web',{}).get('results',[]))

def free_search(query):
    from ddgs import DDGS
    # Explicit backend avoids sending the query to additional search services.
    return DDGS(timeout=15).text(query,backend='duckduckgo',max_results=5)

def sources_from(items):
    sources=[]
    for item in items[:5]:
        url=item.get('url','')
        if not url.startswith('https://'):continue
        sources.append({'label':f'S{len(sources)+1}','name':item.get('title',url),'page':1,'url':url,
            'excerpt':re.sub('<[^>]*>','',item.get('description',''))[:1000],
            'retrieved_at':datetime.now(timezone.utc).isoformat(),'kind':'web'})
    return sources
