"""Live opt-in public search and local whole-document summary smoke checks."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app import web_search
from app.main import answer
from app.summarize import summarize

async def run():
    sources = await web_search.search('Python official documentation')
    assert sources and any('python.org' in s['url'] for s in sources), 'Expected official Python result'
    print('Live free search returned HTTPS sources.')
    response = await answer('Where is the official Python documentation?',[],sources)
    assert response and 'python' in response.lower(), 'Expected an answer about the retrieved Python sources'
    print('Local model answered live search; source cards supplied. Inline model citations: '+str('[S' in response))
    sections = [
        ('Opening','The Orchid project owner is Mira. The launch date is November 18.'),
        ('Middle','The project budget is 42000 rupees. Accessibility testing is mandatory.'),
        ('Ending','The final acceptance condition is offline operation. The backup owner is Ravi.')]
    passages = [{'label':f'S{i+1}','name':'Release fixture','page':i+1,'excerpt':(text+' ')*20,'document_id':0}
                for i,(_,text) in enumerate(sections)]
    result = await summarize(passages,answer)
    assert 'Mira' in result and 'Ravi' in result and 'offline' in result.lower(), result
    print('Real Qwen summary retained opening and ending facts.')

asyncio.run(run())
