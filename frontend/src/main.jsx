import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BookOpen, Check, CircleHelp, Dna, ExternalLink, Library, MessageSquareText, Plus, Search, Send, ShieldCheck} from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App(){
  const [question,setQuestion]=useState('');
  const [messages,setMessages]=useState([]);
  const [busy,setBusy]=useState(false);
  const [health,setHealth]=useState(null);
  const [corpus,setCorpus]=useState({count:0,records:[]});
  const [view,setView]=useState('chat');
  const [sourceQuery,setSourceQuery]=useState('');
  const inputRef=useRef(null);

  useEffect(()=>{
    fetch(`${API}/api/health`).then(r=>r.json()).then(setHealth).catch(()=>setHealth({ready:false}));
    fetch(`${API}/api/corpus`).then(r=>r.json()).then(setCorpus).catch(()=>{});
  },[]);

  const filteredSources=useMemo(()=>{
    const term=sourceQuery.trim().toLowerCase();
    if(!term)return corpus.records;
    return corpus.records.filter(item=>`${item.pmid} ${item.title} ${item.year||''}`.toLowerCase().includes(term));
  },[corpus.records,sourceQuery]);

  async function sendQuestion(value=question){
    const text=value.trim();
    if(!text||busy)return;
    setView('chat');
    setMessages(items=>[...items,{role:'user',text}]);
    setQuestion('');
    setBusy(true);
    try{
      const response=await fetch(`${API}/api/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.detail?.message||'The assistant is unavailable. Check the backend and local Ollama service.');
      setMessages(items=>[...items,{role:'assistant',...data}]);
    }catch(error){
      setMessages(items=>[...items,{role:'error',text:error.message}]);
    }finally{setBusy(false);}
  }

  function newChat(){setMessages([]);setQuestion('');setView('chat');inputRef.current?.focus();}

  return <div className="app-shell">
    <aside className="sidebar" aria-label="Main navigation">
      <button className="brand" onClick={newChat} aria-label="BRCA1 Research Assistant home">
        <span className="brandmark"><Dna size={20}/></span><span className="brandtext">BRCA1<span>RESEARCH</span></span>
      </button>
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav className="nav-list">
        <button className={`nav-item ${view==='chat'?'selected':''}`} onClick={()=>setView('chat')} aria-current={view==='chat'?'page':undefined}>
          <MessageSquareText size={17}/><span>Research chat</span>
        </button>
        <button className={`nav-item ${view==='library'?'selected':''}`} onClick={()=>setView('library')} aria-current={view==='library'?'page':undefined}>
          <Library size={17}/><span>Source library</span>{corpus.count>0&&<span className="nav-count">{corpus.count}</span>}
        </button>
      </nav>
      <div className="sidebar-divider"/>
      <div className="sidebar-note"><ShieldCheck size={16}/><span>Answers stay within the indexed abstracts and link back to PubMed.</span></div>
      <div className="sidebar-bottom">
        <div className="sidebar-foot"><span>BRCA1 LITERATURE REVIEW</span><CircleHelp size={14}/></div>
      </div>
    </aside>

    <main className="main-panel">
      <header className="topbar">
        <div className="breadcrumbs"><span>BRCA1 Research Assistant</span><span className="crumb-separator">/</span><strong>{view==='chat'?'Research chat':'Source library'}</strong></div>
        <div className="top-actions">
          {view==='chat'&&<button className="new-chat-button" onClick={newChat}><Plus size={15}/>New chat</button>}
        </div>
      </header>

      {health!==null&&!health.ready&&<div className="offline-banner" role="status">The assistant is unavailable. Start FastAPI and Ollama, then refresh this page.</div>}
      {view==='chat'?<section className="chat-layout" aria-label="BRCA1 research chat">
        <div className={`conversation ${messages.length===0?'empty-conversation':''}`}>
          {messages.length===0?<div className="welcome">
            <div className="welcome-kicker"><span className="kicker-mark"><Dna size={15}/></span> PUBMED LITERATURE ASSISTANT</div>
            <h1>BRCA1 literature<br/><span>research assistant</span></h1>
            <p className="welcome-copy">Ask focused questions about BRCA1 and breast cancer susceptibility. Responses are based on retrieved PubMed abstracts, include source citations, and identify when the indexed literature does not provide an answer.</p>
            <div className="prompt-card">
              <div className="prompt-heading"><span>QUESTIONS TO EXPLORE</span><span>SELECT TO ASK</span></div>
              <button onClick={()=>sendQuestion('What evidence links inherited BRCA1 mutations with breast cancer susceptibility?')}>What evidence links inherited BRCA1 mutations with breast cancer susceptibility?<span>↗</span></button>
              <button onClick={()=>sendQuestion('Which DNA repair pathways are associated with BRCA1 in the indexed studies?')}>Which DNA repair pathways are associated with BRCA1 in the indexed studies?<span>↗</span></button>
              <button onClick={()=>sendQuestion('What does the corpus report about BRCA1 exon 11 splicing and breast cancer risk?')}>What does the corpus report about BRCA1 exon 11 splicing and breast cancer risk?<span>↗</span></button>
            </div>
          </div>:<div className="thread">
            {messages.map((message,index)=><article className={`message ${message.role}`} key={index}>
              <div className="message-avatar">{message.role==='user'?'Y':message.role==='error'?'!':<Dna size={16}/>}</div>
              <div className="message-body">
                <div className="message-label">{message.role==='user'?'YOU':message.role==='error'?'CONNECTION ISSUE':message.status==='abstained'?'EVIDENCE GAP':'RESEARCH ASSISTANT'}</div>
                <div className="message-text">{message.role==='user'||message.role==='error'?message.text:message.answer}</div>
                {message.role==='assistant'&&message.evidence?.length>0&&<div className="evidence-panel">
                  <div className="evidence-heading"><span>{message.status==='abstained'?'REVIEWED ABSTRACTS':'SOURCES FOR THIS ANSWER'}</span><span>{message.evidence.length} retrieved</span></div>
                  <div className="evidence-list">{message.evidence.map(source=><a className="evidence-card" href={source.source_url} target="_blank" rel="noreferrer" key={source.pmid}>
                    <span className="pmid-badge">PMID {source.pmid}<ExternalLink size={12}/></span><strong>{source.title}</strong><span className="source-meta">{source.year||'Year unavailable'}{source.score!=null?` · Relevance ${Math.round(source.score*100)}%`:''}</span>
                  </a>)}</div>
                </div>}
              </div>
            </article>)}
            {busy&&<div className="thinking"><span className="thinking-icon"><Dna size={15}/></span><span>Searching the indexed literature</span><span className="typing-dots"><i/><i/><i/></span></div>}
          </div>}
        </div>
        <form className="composer" onSubmit={event=>{event.preventDefault();sendQuestion();}}>
          <textarea ref={inputRef} rows="1" value={question} onChange={event=>setQuestion(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendQuestion();}}} placeholder="Ask a research question about BRCA1…" aria-label="Your research question"/>
          <button type="submit" disabled={busy||!question.trim()} aria-label="Send question"><Send size={17}/></button>
          <div className="composer-footer"><span>Answers use retrieved PubMed abstracts only</span><span>Enter to send · Shift+Enter for a new line</span></div>
        </form>
        <div className="research-disclaimer"><ShieldCheck size={14}/><span>For literature research only. Not for diagnosis, individual risk assessment, or clinical decisions.</span></div>
      </section>:<section className="library-layout" aria-label="PubMed source library">
        <div className="library-header"><div className="welcome-kicker"><span className="kicker-mark"><Library size={15}/></span> CORPUS SOURCES</div><h1>Source library</h1><p>Browse the PubMed abstracts available to the assistant. Select a record to open its PubMed page.</p>
          <label className="source-search"><Search size={16}/><input value={sourceQuery} onChange={event=>setSourceQuery(event.target.value)} placeholder="Search by title, PMID, or year…"/><span>{filteredSources.length} records</span></label>
        </div>
        <div className="library-list">{filteredSources.map(source=><a key={source.pmid} className="library-record" href={source.source_url} target="_blank" rel="noreferrer">
          <span className="record-icon"><BookOpen size={17}/></span><span className="record-copy"><strong>{source.title}</strong><span>PMID {source.pmid} <i/> {source.year||'Year unavailable'}</span></span><ExternalLink className="record-external" size={15}/>
        </a>)}{filteredSources.length===0&&<div className="empty-search">No indexed abstracts match “{sourceQuery}”.</div>}</div>
        <div className="library-footer"><span><Check size={14}/> PMID and abstract metadata verified from PubMed E-utilities</span><span>{corpus.count} total records</span></div>
      </section>}
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
