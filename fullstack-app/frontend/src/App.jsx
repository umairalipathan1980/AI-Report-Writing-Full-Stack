import { useMemo, useState } from 'react'
import axios from 'axios'
import { AnimatePresence, motion } from 'framer-motion'
import {
  CheckCircle2,
  CloudUpload,
  FileText,
  Loader,
  Settings2,
  Wand2
} from 'lucide-react'

import { Button } from './components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './components/ui/card'
import { Input } from './components/ui/input'
import { Textarea } from './components/ui/textarea'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [mode, setMode] = useState('recording')
  const [recordingFile, setRecordingFile] = useState(null)
  const [transcript, setTranscript] = useState('')
  const [transcriptFileName, setTranscriptFileName] = useState('')
  const [meetingNotes, setMeetingNotes] = useState('')
  const [additionalInstructions, setAdditionalInstructions] = useState(
    "Do not focus on the company's name in the transcript. Use the same company name as given in the company information."
  )
  const [company, setCompany] = useState({
    company_name: '',
    country: 'Finland',
    consultation_date: '',
    experts: 'Umair Ali Khan, Janne Kauttonen',
    customer_manager: '',
    consultation_type: 'Regular'
  })
  const [useAzure, setUseAzure] = useState(true)
  const [selectedModel, setSelectedModel] = useState('gpt-5.1')
  const [verificationRounds, setVerificationRounds] = useState(5)
  const [useLanggraph, setUseLanggraph] = useState(true)
  const [compressAudio, setCompressAudio] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [reportId, setReportId] = useState('')
  const [results, setResults] = useState(null)
  const [selectedVerificationRound, setSelectedVerificationRound] = useState(1)
  const [authUser, setAuthUser] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authShowPassword, setAuthShowPassword] = useState(false)
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken') || '')

  const missingFields = useMemo(() => {
    const required = [
      ['company_name', 'Company name'],
      ['country', 'Country'],
      ['consultation_date', 'Consultation date'],
      ['experts', 'Experts'],
      ['customer_manager', 'Customer manager'],
      ['consultation_type', 'Consultation type']
    ]
    return required
      .filter(([key]) => !company[key]?.trim())
      .map(([, label]) => label)
  }, [company])

  const handleCompanyChange = (field, value) => {
    setCompany((prev) => ({ ...prev, [field]: value }))
  }

  const handleTranscriptFile = (file) => {
    if (!file) {
      setTranscriptFileName('')
      return
    }
    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result
      if (typeof text === 'string') {
        setTranscript(text)
        setTranscriptFileName(file.name)
      }
    }
    reader.onerror = () => {
      setError('Unable to read transcript file.')
    }
    reader.readAsText(file)
  }

  const resetResults = () => {
    setReportId('')
    setResults(null)
  }

  const handleClearAll = () => {
    setMode('transcript')
    setRecordingFile(null)
    setTranscript('')
    setTranscriptFileName('')
    setMeetingNotes('')
    setAdditionalInstructions(
      "Do not focus on the company's name in the transcript. Use the same company name as given in the company information."
    )
    setCompany({
      company_name: '',
      country: 'Finland',
      consultation_date: '',
      experts: 'Umair Ali Khan, Janne Kauttonen',
      customer_manager: '',
      consultation_type: 'Regular'
    })
    setUseAzure(true)
    setSelectedModel('gpt-5.1')
    setVerificationRounds(5)
    setUseLanggraph(true)
    setCompressAudio(true)
    setError('')
    setSelectedVerificationRound(1)
    resetResults()
  }

  const handleSubmit = async () => {
    if (!authToken) {
      setError('Please log in to generate a report.')
      return
    }
    if (missingFields.length) {
      setError(`Missing required fields: ${missingFields.join(', ')}`)
      return
    }

    if (mode === 'transcript' && !transcript.trim()) {
      setError('Please provide a transcript before generating the report.')
      return
    }

    if (mode === 'recording' && !recordingFile) {
      setError('Please upload a recording before generating the report.')
      return
    }

    try {
      setLoading(true)
      setError('')
      resetResults()

      if (mode === 'transcript') {
        const response = await axios.post(`${API_URL}/reports/from-transcript`, {
          transcript,
          company_data: company,
          meeting_notes: meetingNotes,
          additional_instructions: additionalInstructions,
          use_azure: useAzure,
          selected_model: selectedModel,
          verification_rounds: Number(verificationRounds),
          use_langgraph: useLanggraph
        })
        setReportId(response.data.report_id)
        setResults(response.data.results)
      } else {
        const formData = new FormData()
        formData.append('file', recordingFile)
        formData.append('company_data', JSON.stringify(company))
        formData.append('meeting_notes', meetingNotes)
        formData.append('additional_instructions', additionalInstructions)
        formData.append('use_azure', String(useAzure))
        formData.append('selected_model', selectedModel)
        formData.append('verification_rounds', String(verificationRounds))
        formData.append('compress_audio', String(compressAudio))
        formData.append('use_langgraph', String(useLanggraph))

        const response = await axios.post(`${API_URL}/reports/from-recording`, formData)
        setReportId(response.data.report_id)
        setResults(response.data.results)
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async () => {
    if (!authUser.trim() || !authPassword.trim()) {
      setError('Enter both username and password.')
      return
    }
    try {
      setLoading(true)
      setError('')
      const response = await axios.post(`${API_URL}/auth/login`, {
        username: authUser,
        password: authPassword
      })
      const token = response.data.access_token
      setAuthToken(token)
      localStorage.setItem('authToken', token)
      axios.defaults.headers.common.Authorization = `Bearer ${token}`
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    setAuthToken('')
    localStorage.removeItem('authToken')
    delete axios.defaults.headers.common.Authorization
    setAuthUser('')
    setAuthPassword('')
    setAuthShowPassword(false)
  }

  const latestVerification = results?.verification_history?.slice(-1)[0]
  const downloadUrl = reportId ? `${API_URL}/reports/${reportId}/download` : null
  const htmlUrl = reportId ? `${API_URL}/reports/${reportId}/html` : null
  const verificationHistory = results?.verification_history || []
  const verificationRoundsCount = verificationHistory.length
  const activeVerification =
    verificationHistory[selectedVerificationRound - 1] || latestVerification

  if (authToken) {
    axios.defaults.headers.common.Authorization = `Bearer ${authToken}`
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-ink">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-orchid/30 blur-[120px]" />
        <div className="absolute right-0 top-1/3 h-80 w-80 rounded-full bg-citrine/25 blur-[140px]" />
        <div className="absolute bottom-0 left-1/3 h-96 w-96 rounded-full bg-slate-200/60 blur-[160px]" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="px-6 pt-14 pb-10">
          <div className="mx-auto flex max-w-6xl flex-col items-center text-center">
            <div className="flex flex-col items-center gap-4 md:flex-row md:items-center md:gap-6 md:text-left">
              <div className="flex items-center justify-center rounded-2xl bg-white p-0 shadow-[0_10px_30px_rgba(15,23,42,0.12)]">
                <img
                  src="/fair.png"
                  alt="FAIR logo"
                  className="h-24 w-32 object-contain bg-white"
                />
              </div>
              <div className="text-center md:text-left">
                <h1 className="text-3xl font-display tracking-tight text-slate-900 md:text-6xl">
                  Report Writing Studio
                </h1>
                <p className="mt-3 max-w-3xl text-base text-slate-600 md:text-lg">
                  Convert meeting recordings or transcripts into structured reports.
                </p>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 px-6 pb-16">
          <div className="mx-auto flex max-w-6xl flex-col gap-8">
            {!authToken && (
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="mx-auto w-full max-w-3xl"
              >
                <Card className="border-slate-200 bg-white/90 shadow-[0_30px_70px_rgba(15,23,42,0.12)] backdrop-blur">
                <CardHeader>
                  <CardTitle className="text-xl">Sign in</CardTitle>
                  <CardDescription>Enter your credentials to access the report studio.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Username</label>
                      <Input
                        value={authUser}
                        onChange={(event) => setAuthUser(event.target.value)}
                        placeholder="Username"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Password</label>
                      <Input
                        type={authShowPassword ? 'text' : 'password'}
                        value={authPassword}
                        onChange={(event) => setAuthPassword(event.target.value)}
                        placeholder="Password"
                      />
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <input
                          type="checkbox"
                          checked={authShowPassword}
                          onChange={(event) => setAuthShowPassword(event.target.checked)}
                          className="h-4 w-4"
                        />
                        <span>Show password</span>
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button type="button" className="w-full" onClick={handleLogin} disabled={loading}>
                      {loading ? (
                        <>
                          <Loader className="h-4 w-4 animate-spin" />
                          Signing in...
                        </>
                      ) : (
                        'Sign in'
                      )}
                    </Button>
                  </CardFooter>
                  {error && (
                    <div className="px-6 pb-6">
                      <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                        {error}
                      </div>
                    </div>
                  )}
                </Card>
              </motion.section>
            )}

            {authToken && (
            <motion.section
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              className="mx-auto w-full max-w-5xl"
            >
              <details className="group rounded-3xl border border-slate-200 bg-white/90 shadow-[0_24px_60px_rgba(15,23,42,0.12)] backdrop-blur">
                <summary className="flex cursor-pointer items-center justify-between px-6 py-5 text-lg font-semibold text-slate-800">
                  <span className="flex items-center gap-2">
                    <Settings2 className="h-4 w-4 text-slate-700" />
                    Workflow Settings
                  </span>
                  <span className="text-sm font-medium text-slate-500 group-open:hidden">Show</span>
                  <span className="text-sm font-medium text-slate-500 hidden group-open:inline">Hide</span>
                </summary>
                <div className="border-t border-slate-200 px-6 pb-6 pt-4">
                  <p className="text-sm text-slate-500">
                    Match the original Streamlit controls without changing report logic.
                  </p>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={useAzure}
                        onChange={(event) => setUseAzure(event.target.checked)}
                        className="h-4 w-4"
                      />
                      <span className="text-sm text-slate-700">Use Azure endpoint</span>
                    </div>
                    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={useLanggraph}
                        onChange={(event) => setUseLanggraph(event.target.checked)}
                        className="h-4 w-4"
                      />
                      <span className="text-sm text-slate-700">Use LangGraph workflow</span>
                    </div>
                    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={compressAudio}
                        onChange={(event) => setCompressAudio(event.target.checked)}
                        className="h-4 w-4"
                        disabled={mode !== 'recording'}
                      />
                      <span className="text-sm text-slate-700">Compress audio</span>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Verification rounds</label>
                      <Input
                        type="number"
                        min={1}
                        max={5}
                        value={verificationRounds}
                        onChange={(event) => setVerificationRounds(event.target.value)}
                      />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <label className="text-sm font-medium text-slate-700">Model selection</label>
                      <select
                        value={selectedModel}
                        onChange={(event) => setSelectedModel(event.target.value)}
                        className="h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700"
                      >
                        <option value="gpt-4.1">gpt-4.1</option>
                        <option value="gpt-5.1">gpt-5.1</option>
                        <option value="gpt-5.2">gpt-5.2</option>
                      </select>
                    </div>
                  </div>
                </div>
              </details>
            </motion.section>
            )}

            {authToken && (
            <motion.section
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: 'easeOut', delay: 0.1 }}
              className="mx-auto w-full max-w-5xl"
            >
              <Card className="border-slate-200 bg-white/90 shadow-[0_40px_90px_rgba(15,23,42,0.15)] backdrop-blur">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Wand2 className="h-5 w-5 text-slate-700" />
                    Create Report
                  </CardTitle>
                  <CardDescription>
                    Provide a transcript or upload a recording, then add company details and
                    optional guidance.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      variant={mode === 'recording' ? 'default' : 'outline'}
                      className="gap-2"
                      onClick={() => setMode('recording')}
                    >
                      <CloudUpload className="h-4 w-4" />
                      Recording
                    </Button>
                    <Button
                      type="button"
                      variant={mode === 'transcript' ? 'default' : 'outline'}
                      className="gap-2"
                      onClick={() => setMode('transcript')}
                    >
                      <FileText className="h-4 w-4" />
                      Transcript
                    </Button>
                  </div>

                  {mode === 'recording' ? (
                    <div className="space-y-3">
                      <label className="text-sm font-medium text-slate-700">
                        Upload recording
                      </label>
                      <Input
                        type="file"
                        accept=".mp3,.mp4,.wav,.m4a,.ogg,.mpeg,.mpga,.avi,.mov"
                        onChange={(event) => setRecordingFile(event.target.files?.[0] || null)}
                      />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">
                          Upload transcript (.txt)
                        </label>
                        <Input
                          type="file"
                          accept=".txt"
                          onChange={(event) => handleTranscriptFile(event.target.files?.[0] || null)}
                        />
                        {transcriptFileName && (
                          <p className="text-xs text-slate-500">Loaded: {transcriptFileName}</p>
                        )}
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700">
                          Paste transcript
                        </label>
                        <Textarea
                          value={transcript}
                          onChange={(event) => setTranscript(event.target.value)}
                          placeholder="Paste the full transcript here..."
                          className="min-h-[180px]"
                        />
                      </div>
                    </div>
                  )}

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Company name</label>
                      <Input
                        value={company.company_name}
                        onChange={(event) => handleCompanyChange('company_name', event.target.value)}
                        placeholder="Company name"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Country</label>
                      <Input
                        value={company.country}
                        onChange={(event) => handleCompanyChange('country', event.target.value)}
                        placeholder="Finland"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Consultation date</label>
                      <Input
                        value={company.consultation_date}
                        onChange={(event) => handleCompanyChange('consultation_date', event.target.value)}
                        placeholder="11-03-2025"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Experts</label>
                      <Input
                        value={company.experts}
                        onChange={(event) => handleCompanyChange('experts', event.target.value)}
                        placeholder="Maria Rodriguez, Alex Chen"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Customer manager</label>
                      <Input
                        value={company.customer_manager}
                        onChange={(event) => handleCompanyChange('customer_manager', event.target.value)}
                        placeholder="Jamie Park"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Consultation type</label>
                      <Input
                        value={company.consultation_type}
                        onChange={(event) => handleCompanyChange('consultation_type', event.target.value)}
                        placeholder="Regular"
                      />
                    </div>
                  </div>

                  <div className="grid gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Meeting notes</label>
                      <Textarea
                        value={meetingNotes}
                        onChange={(event) => setMeetingNotes(event.target.value)}
                        placeholder="Optional notes captured during the session..."
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700">Additional instructions</label>
                      <Textarea
                        value={additionalInstructions}
                        onChange={(event) => setAdditionalInstructions(event.target.value)}
                        placeholder="Optional constraints or extra guidance..."
                      />
                    </div>
                  </div>
                </CardContent>
                <CardFooter className="flex flex-col gap-4">
                  <Button
                    type="button"
                    className="w-full gap-2"
                    onClick={handleSubmit}
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <Loader className="h-4 w-4 animate-spin" />
                        Generating report...
                      </>
                    ) : (
                      <>
                        <Wand2 className="h-4 w-4" />
                        Generate Report
                      </>
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={handleClearAll}
                    disabled={loading}
                  >
                    Clear All Fields
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={handleLogout}
                    disabled={loading}
                  >
                    Log out
                  </Button>
                  <AnimatePresence>
                    {error && (
                      <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        className="w-full rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600"
                      >
                        {error}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </CardFooter>
              </Card>
            </motion.section>
            )}

            {results && authToken && (
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: 'easeOut', delay: 0.2 }}
                className="mx-auto w-full max-w-5xl"
              >
                <Card className="border-slate-200 bg-white/90 shadow-[0_30px_70px_rgba(15,23,42,0.12)] backdrop-blur">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-xl">
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                      Report Output
                    </CardTitle>
                    <CardDescription>
                      Review workflow status and download the final report once ready.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-700">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">Status</span>
                        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                          {results.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="font-medium">Report ID</span>
                        <span className="text-xs text-slate-500">{reportId}</span>
                      </div>
                      {latestVerification && (
                        <div className="flex items-center justify-between">
                          <span className="font-medium">Latest score</span>
                          <span className="text-sm font-semibold text-emerald-600">
                            {latestVerification.score}/10
                          </span>
                        </div>
                      )}
                      <div className="text-xs text-slate-500">
                        Verification rounds: {verificationRoundsCount}
                      </div>
                    </div>

                    <div className="flex flex-col gap-3">
                      {downloadUrl && (
                        <Button asChild className="w-full">
                          <a href={downloadUrl}>Download DOCX</a>
                        </Button>
                      )}
                      {htmlUrl && (
                        <Button asChild variant="outline" className="w-full">
                          <a href={htmlUrl} target="_blank" rel="noreferrer">
                            Open HTML preview
                          </a>
                        </Button>
                      )}
                    </div>

                    {verificationRoundsCount > 0 && (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-700">
                        <div className="flex flex-wrap items-center gap-2">
                          {verificationHistory.map((_, index) => {
                            const roundNumber = index + 1
                            const isActive = roundNumber === selectedVerificationRound
                            return (
                              <button
                                key={`verification-round-${roundNumber}`}
                                type="button"
                                onClick={() => setSelectedVerificationRound(roundNumber)}
                                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                                  isActive
                                    ? 'bg-slate-900 text-white'
                                    : 'bg-white text-slate-600 hover:bg-slate-200'
                                }`}
                              >
                                Round {roundNumber}
                              </button>
                            )
                          })}
                        </div>

                        <div className="mt-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Score
                            </span>
                            <span className="text-sm font-semibold text-emerald-600">
                              {activeVerification?.score ?? 'N/A'}/10
                            </span>
                          </div>
                          {activeVerification?.summary && (
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                Summary
                              </p>
                              <p className="mt-2">{activeVerification.summary}</p>
                            </div>
                          )}
                          {activeVerification?.decision_explanation && (
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                Decision
                              </p>
                              <p className="mt-2">{activeVerification.decision_explanation}</p>
                            </div>
                          )}
                          <div className="space-y-2">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Issues
                            </p>
                            {activeVerification?.issues?.length ? (
                              <div className="space-y-2">
                                {activeVerification.issues.map((issue, idx) => (
                                  <div
                                    key={`issue-${idx}`}
                                    className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-slate-700"
                                  >
                                    <p className="font-semibold">
                                      {issue.type || 'Issue'} · {issue.section || 'General'}
                                    </p>
                                    <p className="mt-1 text-slate-600">{issue.description}</p>
                                    <p className="mt-1 text-slate-500">
                                      Suggestion: {issue.suggestion || 'n/a'}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-xs text-slate-500">No issues found.</p>
                            )}
                          </div>
                          <div className="space-y-2">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                              Strengths
                            </p>
                            {activeVerification?.strengths?.length ? (
                              <div className="space-y-2">
                                {activeVerification.strengths.map((strength, idx) => (
                                  <div
                                    key={`strength-${idx}`}
                                    className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-slate-700"
                                  >
                                    {strength}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-xs text-slate-500">No strengths listed.</p>
                            )}
                          </div>
                          {results?.revision_history?.[selectedVerificationRound - 1]?.revision_summary && (
                            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                                Revision Summary
                              </p>
                              <p className="mt-2">
                                {results.revision_history[selectedVerificationRound - 1].revision_summary}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {latestVerification?.summary && (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Latest summary
                        </p>
                        <p className="mt-2">{latestVerification.summary}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.section>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
