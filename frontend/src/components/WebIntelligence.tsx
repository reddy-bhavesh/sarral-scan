import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Globe, Server, Lock, Search, Link as LinkIcon, Mail, Phone, Hash, Code } from 'lucide-react';

interface WebIntelligenceProps {
  data: any;
}

const Section = ({ title, icon: Icon, children, defaultOpen = false }: { title: string; icon: any; children: React.ReactNode; defaultOpen?: boolean }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg bg-white dark:bg-gray-900/50 mb-4 overflow-hidden shadow-sm">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          <h3 className="font-semibold text-gray-900 dark:text-gray-200">{title}</h3>
        </div>
        {isOpen ? <ChevronUp className="w-5 h-5 text-gray-500 dark:text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-500 dark:text-gray-400" />}
      </button>
      {isOpen && <div className="p-4 border-t border-gray-200 dark:border-gray-800">{children}</div>}
    </div>
  );
};

const KeyValue = ({ label, value }: { label: string; value: any }) => (
  <div className="flex justify-between py-2 border-b border-gray-200 dark:border-gray-800 last:border-0">
    <span className="text-gray-600 dark:text-gray-400">{label}</span>
    <span className="text-gray-900 dark:text-gray-200 font-mono text-sm text-right">{value || 'N/A'}</span>
  </div>
);

const Badge = ({ children, color = 'blue' }: { children: React.ReactNode; color?: string }) => {
  const colors: any = {
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    green: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800',
    red: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800',
    purple: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-800',
  };
  return (
    <span className={`px-2 py-1 rounded text-xs border ${colors[color]} mr-2 mb-2 inline-block`}>
      {children}
    </span>
  );
};

export default function WebIntelligence({ data }: WebIntelligenceProps) {
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  if (!data) return <div className="text-gray-500 dark:text-gray-400 p-4">No Web Intelligence data available.</div>;

  // Detect if data is multi-target (dict of objects) or single-target
  const isMultiTarget = !data.target && Object.keys(data).length > 0;
  
  // Get the list of domains if multi-target (only ALIVE ones)
  const domains = isMultiTarget 
    ? Object.keys(data).filter(d => data[d]?.alive).sort() 
    : [];
  
  // Set default selection
  if (isMultiTarget && !selectedDomain && domains.length > 0) {
    // Try to find the main domain (shortest one usually) or just the first
    setSelectedDomain(domains[0]);
  }

  // Determine which data object to show
  const currentData = isMultiTarget 
    ? (selectedDomain ? data[selectedDomain] : null) 
    : data;

  if (!currentData) return <div className="text-gray-500 dark:text-gray-400 p-4">Select a domain to view details.</div>;

  return (
    <div className="space-y-4">
      {/* Domain Selector for Multi-Target Mode */}
      {isMultiTarget && (
        <div className="bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-800 mb-6 shadow-sm">
          <label className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">Select Subdomain ({domains.length} scanned)</label>
          <select 
            value={selectedDomain || ''} 
            onChange={(e) => setSelectedDomain(e.target.value)}
            className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {domains.map(d => (
              <option key={d} value={d}>{d} {data[d]?.alive ? '(ALIVE)' : '(DEAD)'}</option>
            ))}
          </select>
        </div>
      )}

      {/* SECTION A - Overview */}
      <Section title="Overview" icon={Globe} defaultOpen={true}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <KeyValue label="Target" value={currentData.target} />
            <KeyValue label="Final URL" value={currentData.http_probe?.final_url} />
            <KeyValue label="Status" value={
              <span className={currentData.alive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                {currentData.alive ? "ALIVE" : "DEAD"}
              </span>
            } />
            <KeyValue label="WAF" value={currentData.waf || "None Detected"} />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2">Technologies</h4>
            <div className="flex flex-wrap">
              {currentData.technologies?.map((tech: string) => (
                <Badge key={tech} color="blue">{tech}</Badge>
              ))}
              {(!currentData.technologies || currentData.technologies.length === 0) && <span className="text-gray-500 text-sm">None detected</span>}
            </div>
            
            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mt-4 mb-2">Resolved IPs</h4>
            <div className="flex flex-wrap">
              {currentData.resolved_ips?.map((ip: string) => (
                <Badge key={ip} color="purple">{ip}</Badge>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* SECTION C - HTTP Fingerprint */}
      <Section title="HTTP Fingerprint" icon={Server}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
             <KeyValue label="Status Code" value={currentData.http_probe?.status_code} />
             <KeyValue label="Server" value={currentData.headers?.Server} />
             <KeyValue label="Content Length" value={currentData.http_probe?.content_length} />
             <KeyValue label="Favicon Hash (MD5)" value={currentData.favicon_hash?.md5} />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2">HTTP Methods</h4>
             <div className="flex flex-wrap">
              {currentData.http_methods?.map((m: string) => (
                <Badge key={m} color="green">{m}</Badge>
              ))}
            </div>

            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mt-4 mb-2">Security Headers</h4>
            <div className="space-y-1">
              {Object.entries(currentData.security_headers || {}).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="text-gray-500 capitalize">{k.replace(/_/g, ' ')}</span>
                  <span className={v ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>{v ? "Present" : "Missing"}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* SECTION D - TLS Certificate */}
      <Section title="TLS Certificate" icon={Lock}>
        {currentData.tls_info ? (
          <div className="space-y-2">
            <KeyValue label="Issuer" value={currentData.tls_info.issuer} />
            <KeyValue label="Subject" value={currentData.tls_info.subject} />
            <KeyValue label="Valid From" value={currentData.tls_info.not_before} />
            <KeyValue label="Valid To" value={currentData.tls_info.not_after} />
            <div className="mt-2">
              <span className="text-gray-600 dark:text-gray-400 text-sm block mb-1">SAN Entries</span>
              <div className="flex flex-wrap gap-2">
                {currentData.tls_info.san?.map((san: string) => (
                  <span key={san} className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 px-2 py-1 rounded">{san}</span>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-gray-500">No TLS information available.</div>
        )}
      </Section>

      {/* SECTION E - OSINT Data */}
      <Section title="OSINT Data" icon={Search}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2"><Mail className="w-4 h-4"/> Emails</h4>
            <ul className="list-disc list-inside text-sm text-gray-700 dark:text-gray-300 space-y-1">
              {currentData.emails?.map((e: string) => <li key={e}>{e}</li>)}
              {(!currentData.emails || currentData.emails.length === 0) && <li className="text-gray-500 list-none">No emails found</li>}
            </ul>

            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mt-4 mb-2 flex items-center gap-2"><Phone className="w-4 h-4"/> Phones</h4>
            <ul className="list-disc list-inside text-sm text-gray-700 dark:text-gray-300 space-y-1">
              {currentData.phones?.map((p: string) => <li key={p}>{p}</li>)}
              {(!currentData.phones || currentData.phones.length === 0) && <li className="text-gray-500 list-none">No phones found</li>}
            </ul>
          </div>
          <div>
             <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2"><LinkIcon className="w-4 h-4"/> Social Profiles</h4>
             <ul className="list-disc list-inside text-sm text-gray-700 dark:text-gray-300 space-y-1">
              {currentData.social_profiles?.map((s: string) => {
                const href = s.startsWith('http') ? s : `https://${s}`;
                return (
                  <li key={s}><a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline truncate block">{s}</a></li>
                );
              })}
              {(!currentData.social_profiles || currentData.social_profiles.length === 0) && <li className="text-gray-500 list-none">No profiles found</li>}
            </ul>

            <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mt-4 mb-2 flex items-center gap-2"><Hash className="w-4 h-4"/> Internal IPs</h4>
             <ul className="list-disc list-inside text-sm text-gray-700 dark:text-gray-300 space-y-1">
              {currentData.internal_ips?.map((ip: string) => <li key={ip}>{ip}</li>)}
              {(!currentData.internal_ips || currentData.internal_ips.length === 0) && <li className="text-gray-500 list-none">No internal IPs found</li>}
            </ul>
          </div>
        </div>
        
        {currentData.comments && currentData.comments.length > 0 && (
          <div className="mt-4">
             <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2 flex items-center gap-2"><Code className="w-4 h-4"/> Interesting Comments</h4>
             <div className="bg-gray-100 dark:bg-black/30 p-3 rounded text-xs font-mono text-gray-600 dark:text-gray-400 max-h-40 overflow-y-auto">
               {currentData.comments.map((c: string, i: number) => (
                 <div key={i} className="mb-1 border-b border-gray-200 dark:border-gray-800 pb-1 last:border-0">{c}</div>
               ))}
             </div>
          </div>
        )}
      </Section>

      {/* SECTION F - Crawl Results */}
      <Section title="Crawl Results" icon={LinkIcon}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
           <div>
             <KeyValue label="Pages Visited" value={currentData.pages_visited} />
             <KeyValue label="Max Depth" value={currentData.max_depth} />
             <KeyValue label="Duration" value={`${currentData.duration_sec}s`} />
           </div>
           <div>
             <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2">API Endpoints</h4>
             <div className="max-h-32 overflow-y-auto bg-gray-100 dark:bg-black/30 p-2 rounded">
                <ul className="list-none text-xs text-gray-700 dark:text-gray-300 space-y-1">
                  {currentData.api_endpoints?.map((e: string) => <li key={e} className="truncate">{e}</li>)}
                  {(!currentData.api_endpoints || currentData.api_endpoints.length === 0) && <li className="text-gray-500">No endpoints found</li>}
                </ul>
             </div>
           </div>
        </div>
        
        <div className="mt-4">
           <h4 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-2">Visited URLs</h4>
           <div className="max-h-40 overflow-y-auto bg-gray-100 dark:bg-black/30 p-2 rounded">
              <ul className="list-none text-xs text-gray-700 dark:text-gray-300 space-y-1">
                {currentData.visited_urls?.map((u: string) => (
                  <li key={u} className="truncate hover:text-blue-600 dark:hover:text-blue-400"><a href={u} target="_blank" rel="noopener noreferrer">{u}</a></li>
                ))}
              </ul>
           </div>
        </div>
      </Section>
    </div>
  );
}
