'use client'

const COMMON = [
  ['project_name', 'Cloud project / site / app name'],
  ['repository_name', 'GitHub repository name'],
  ['commit_message', 'Deployment commit message'],
]
const PROVIDER = {
  vercel: [['vercel_scope', 'Vercel team scope (optional)']],
  netlify: [['netlify_team', 'Netlify team slug (optional)'], ['netlify_site_id', 'Existing Netlify site ID (optional)']],
  azure: [['azure_resource_group', 'Resource group'], ['azure_plan', 'App Service plan name'], ['azure_location', 'Azure location']],
}
const INPUT = 'mt-1 w-full rounded-xl border border-[rgba(145,158,171,0.2)] bg-[#141A21] px-3.5 py-2 text-[12px] text-white outline-none focus:border-[#1877F2] focus:ring-1 focus:ring-[#1877F2] transition-colors placeholder:text-[#919EAB]/50'

export default function DeployInterview({ project, target, value, onChange, redeploy }) {
  const patch = (key, text) => onChange({ ...value, [key]: text })
  return <section className="mt-5 rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#141A21]/60 p-4">
    <p className="text-[13px] font-semibold text-white">Deployment choices</p>
    <p className="mt-1 text-[11px] text-[#919EAB]">{redeploy ? 'This update uses your recorded repository and cloud destination.' : 'Choose names and provider settings before the agent starts.'}</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      {[...COMMON, ...(PROVIDER[target] || [])].map(([key, label]) => <label key={key} className="text-[11px] text-[#919EAB]">
        {label}<input className={INPUT} value={value[key] || ''} onChange={e => patch(key, e.target.value)}
          disabled={redeploy && key !== 'commit_message'} placeholder={key.endsWith('name') ? project : key === 'azure_location' ? 'centralindia' : 'Optional'} />
      </label>)}
      <label className="text-[11px] text-[#919EAB]">GitHub visibility
        <select className={INPUT} disabled={redeploy} value={value.repository_visibility || 'private'} onChange={e => patch('repository_visibility', e.target.value)}>
          <option className="bg-[#1C252E] text-white" value="private">Private</option><option className="bg-[#1C252E] text-white" value="public">Public</option>
        </select>
      </label>
      {target === 'aws_ec2' && <label className="text-[11px] text-[#919EAB]">EC2 instance size
        <select className={INPUT} value={value.aws_instance_type || 't3.micro'} onChange={e => patch('aws_instance_type', e.target.value)}>
          {['t3.micro', 't3.small', 't3.medium', 't4g.micro', 't4g.small'].map(size => <option className="bg-[#1C252E] text-white" key={size}>{size}</option>)}
        </select>
      </label>}
      {target === 'azure' && <label className="text-[11px] text-[#919EAB]">App Service plan size
        <select className={INPUT} value={value.azure_sku || 'B1'} onChange={e => patch('azure_sku', e.target.value)}>
          {['F1', 'B1', 'B2', 'B3', 'S1', 'P1v3'].map(size => <option className="bg-[#1C252E] text-white" key={size}>{size}</option>)}
        </select>
      </label>}
    </div>
    <label className="mt-3 block text-[11px] text-[#919EAB]">GitHub README content (leave empty to keep the current README)
      <textarea className={INPUT} rows={3} value={value.readme || ''} onChange={e => patch('readme', e.target.value)} placeholder="Describe the app, setup and deployment…" />
    </label>
  </section>
}
