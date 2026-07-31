import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { loans as loansApi, categories as categoriesApi, type LoanFormInput } from '@/lib/api'
import { useDisplayLocale, useDateLocale } from '@/hooks/use-display-locale'
import { formatCurrency } from '@/lib/format'
import { localDateString } from '@/lib/date-utils'
import { usePrivacyMode } from '@/hooks/use-privacy-mode'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DatePickerInput } from '@/components/ui/date-picker-input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import type { LoanSummary } from '@/types'
import {
  Landmark,
  Plus,
  Pencil,
  Trash2,
  ChevronDown,
  ChevronRight,
  Upload,
  Download,
  CheckCircle2,
  Circle,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

const emptyForm: LoanFormInput = {
  name: '',
  currency: 'BRL',
  principal_amount: 0,
  interest_rate: 0,
  rate_period: 'annual',
  amortization_system: 'sac',
  term_months: 0,
  start_date: localDateString(),
  insurance_monthly: null,
  admin_fee_monthly: null,
  payment_category_id: null,
}

export function LoansTab({ canWrite }: { canWrite: boolean }) {
  const { t } = useTranslation()
  const locale = useDisplayLocale()
  const { mask } = usePrivacyMode()
  const queryClient = useQueryClient()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingLoan, setEditingLoan] = useState<LoanSummary | null>(null)
  const [expandedLoanId, setExpandedLoanId] = useState<string | null>(null)
  const [deletingLoanId, setDeletingLoanId] = useState<string | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)

  const { data: loansList, isLoading } = useQuery({
    queryKey: ['loans'],
    queryFn: () => loansApi.list(),
  })

  const { data: categoriesList } = useQuery({
    queryKey: ['categories'],
    queryFn: categoriesApi.list,
  })

  const invalidateLoans = () => {
    queryClient.invalidateQueries({ queryKey: ['loans'] })
    queryClient.invalidateQueries({ queryKey: ['loan-installments'] })
  }

  const createMutation = useMutation({
    mutationFn: (data: LoanFormInput) => loansApi.create(data),
    onSuccess: () => {
      invalidateLoans()
      setDialogOpen(false)
      toast.success(t('loans.created'))
    },
    onError: () => toast.error(t('common.error')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: LoanFormInput }) => loansApi.update(id, data),
    onSuccess: () => {
      invalidateLoans()
      setDialogOpen(false)
      setEditingLoan(null)
      toast.success(t('loans.updated'))
    },
    onError: () => toast.error(t('common.error')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => loansApi.delete(id),
    onSuccess: () => {
      invalidateLoans()
      setDeletingLoanId(null)
      toast.success(t('loans.deleted'))
    },
    onError: () => toast.error(t('common.error')),
  })

  const importMutation = useMutation({
    mutationFn: () => loansApi.importFile(importFile!),
    onSuccess: (data) => {
      invalidateLoans()
      setImportOpen(false)
      setImportFile(null)
      if (data.errors.length > 0) {
        toast.warning(t('loans.importPartial', { created: data.created, updated: data.updated, errors: data.errors.length }))
      } else {
        toast.success(t('loans.importSuccess', { created: data.created, updated: data.updated }))
      }
    },
    onError: () => toast.error(t('common.error')),
  })

  const openCreate = () => { setEditingLoan(null); setDialogOpen(true) }
  const openEdit = (loan: LoanSummary) => { setEditingLoan(loan); setDialogOpen(true) }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-2">
        {canWrite && (
          <>
            <Button variant="outline" onClick={() => setImportOpen(true)} className="gap-1.5">
              <Upload size={16} />
              {t('loans.import')}
            </Button>
            <Button onClick={openCreate} className="gap-1.5">
              <Plus size={16} />
              {t('loans.add')}
            </Button>
          </>
        )}
      </div>

      {isLoading ? (
        <div className="bg-card rounded-xl border border-border p-8 text-center text-muted-foreground">
          {t('common.loading')}
        </div>
      ) : !loansList || loansList.length === 0 ? (
        <div className="bg-card rounded-xl border border-border p-8 text-center text-muted-foreground">
          <Landmark size={28} className="mx-auto mb-2 opacity-50" />
          {t('loans.empty')}
        </div>
      ) : (
        <div className="space-y-3">
          {loansList.map((loan) => (
            <LoanCard
              key={loan.details.id}
              loan={loan}
              expanded={expandedLoanId === loan.details.id}
              onToggle={() => setExpandedLoanId(expandedLoanId === loan.details.id ? null : loan.details.id)}
              canWrite={canWrite}
              locale={locale}
              mask={mask}
              onEdit={() => openEdit(loan)}
              onDelete={() => setDeletingLoanId(loan.details.id)}
            />
          ))}
        </div>
      )}

      <LoanFormDialog
        open={dialogOpen}
        onClose={() => { setDialogOpen(false); setEditingLoan(null) }}
        loan={editingLoan}
        categories={categoriesList ?? []}
        onSave={(data) => {
          if (editingLoan) {
            updateMutation.mutate({ id: editingLoan.details.id, data })
          } else {
            createMutation.mutate(data)
          }
        }}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      <Dialog open={!!deletingLoanId} onOpenChange={() => setDeletingLoanId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('loans.confirmDeleteTitle')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{t('loans.confirmDelete')}</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingLoanId(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => deletingLoanId && deleteMutation.mutate(deletingLoanId)}
              disabled={deleteMutation.isPending}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={(open) => { if (!open) { setImportOpen(false); setImportFile(null) } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('loans.import')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{t('loans.importHint')}</p>
            <button
              type="button"
              className="text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
              onClick={() => {
                const csv = 'name,principal_amount,interest_rate,rate_period,amortization_system,term_months,start_date,insurance_monthly,admin_fee_monthly,payment_category_name,currency\n'
                  + 'Financiamento Apto,300000,10.5,annual,sac,360,2026-08-10,45.00,25.00,Moradia,BRL\n'
                const blob = new Blob([csv], { type: 'text/csv' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = 'securo-loans-template.csv'
                a.click()
                URL.revokeObjectURL(url)
              }}
            >
              <Download size={12} />
              {t('import.downloadTemplate')}
            </button>
            <div className="space-y-2">
              <Label>{t('assets.importFile')}</Label>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-muted-foreground file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-muted file:text-foreground file:text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setImportOpen(false); setImportFile(null) }}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => importMutation.mutate()}
              disabled={!importFile || importMutation.isPending}
            >
              {importMutation.isPending ? t('common.loading') : t('import.title')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function LoanCard({
  loan,
  expanded,
  onToggle,
  canWrite,
  locale,
  mask,
  onEdit,
  onDelete,
}: {
  loan: LoanSummary
  expanded: boolean
  onToggle: () => void
  canWrite: boolean
  locale: string
  mask: (v: string) => string
  onEdit: () => void
  onDelete: () => void
}) {
  const { t } = useTranslation()
  const dateLocale = useDateLocale()
  const { details } = loan
  const progressPct = loan.installments_total > 0 ? (loan.installments_paid / loan.installments_total) * 100 : 0

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
      <div className="flex items-center gap-3 px-4 sm:px-5 py-4">
        <button onClick={onToggle} className="flex items-center gap-3 flex-1 min-w-0 text-left">
          {expanded ? <ChevronDown size={14} className="text-muted-foreground shrink-0" /> : <ChevronRight size={14} className="text-muted-foreground shrink-0" />}
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-orange-100">
            <Landmark size={16} className="text-orange-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground truncate">{details.name}</span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border uppercase shrink-0">
                {details.amortization_system}
              </span>
            </div>
            <span className="text-xs text-muted-foreground">
              {t('loans.progress', { paid: loan.installments_paid, total: loan.installments_total })}
            </span>
          </div>
        </button>
        <div className="text-right shrink-0">
          <p className="text-sm font-bold tabular-nums text-foreground">
            {mask(formatCurrency(loan.outstanding_balance, details.currency, locale))}
          </p>
          {loan.next_installment && (
            <p className="text-xs text-muted-foreground">
              {t('loans.nextDue')}: {new Date(`${loan.next_installment.due_date}T00:00:00`).toLocaleDateString(dateLocale)}
            </p>
          )}
        </div>
        {canWrite && (
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={onEdit} className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-primary/5 transition-colors" title={t('common.edit')}>
              <Pencil size={13} />
            </button>
            <button onClick={onDelete} className="p-1.5 rounded-md text-muted-foreground hover:text-rose-500 hover:bg-rose-50 transition-colors" title={t('common.delete')}>
              <Trash2 size={13} />
            </button>
          </div>
        )}
      </div>
      {expanded && <LoanScheduleDetail loanId={details.id} currency={details.currency} canWrite={canWrite} />}
    </div>
  )
}

function LoanScheduleDetail({ loanId, currency, canWrite }: { loanId: string; currency: string; canWrite: boolean }) {
  const { t } = useTranslation()
  const locale = useDisplayLocale()
  const dateLocale = useDateLocale()
  const { mask } = usePrivacyMode()
  const queryClient = useQueryClient()

  const { data: installments } = useQuery({
    queryKey: ['loan-installments', loanId],
    queryFn: () => loansApi.installments(loanId),
  })

  const markPaidMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'paid' | 'projected' }) =>
      loansApi.markInstallment(loanId, id, {
        status,
        paid_date: status === 'paid' ? localDateString() : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loans'] })
      queryClient.invalidateQueries({ queryKey: ['loan-installments', loanId] })
    },
    onError: () => toast.error(t('common.error')),
  })

  const formatDate = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(dateLocale)
  const chartData = (installments ?? []).map((i) => ({ date: i.due_date, balance: i.outstanding_balance_after }))

  return (
    <div className="border-t border-border">
      {chartData.length > 0 && (
        <div className="p-4 border-b border-border">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                tickFormatter={(d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(dateLocale, { month: 'short', year: '2-digit' })}
                minTickGap={40}
              />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => mask(formatCurrency(v, currency, locale))} width={70} />
              <Tooltip
                formatter={(v: number) => mask(formatCurrency(v, currency, locale))}
                labelFormatter={(d: string) => formatDate(d)}
              />
              <Area type="monotone" dataKey="balance" stroke="#f97316" fill="#f97316" fillOpacity={0.15} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="overflow-x-auto max-h-96 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-card">
            <tr className="border-b border-border">
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">#</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">{t('loans.dueDate')}</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">{t('loans.amortization')}</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">{t('loans.interest')}</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground">{t('loans.total')}</th>
              <th className="text-right px-3 py-2 font-medium text-muted-foreground hidden sm:table-cell">{t('loans.balanceAfter')}</th>
              {canWrite && <th className="text-center px-3 py-2 font-medium text-muted-foreground">{t('loans.status')}</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {(installments ?? []).map((row) => (
              <tr key={row.id} className={row.status === 'paid' ? 'bg-emerald-50/40' : ''}>
                <td className="px-3 py-2 text-muted-foreground">{row.installment_number}</td>
                <td className="px-3 py-2 whitespace-nowrap">{formatDate(row.due_date)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{mask(formatCurrency(row.amortization_amount, currency, locale))}</td>
                <td className="px-3 py-2 text-right tabular-nums">{mask(formatCurrency(row.interest_amount, currency, locale))}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">{mask(formatCurrency(row.total_amount, currency, locale))}</td>
                <td className="px-3 py-2 text-right tabular-nums hidden sm:table-cell text-muted-foreground">
                  {mask(formatCurrency(row.outstanding_balance_after, currency, locale))}
                </td>
                {canWrite && (
                  <td className="px-3 py-2 text-center">
                    <button
                      type="button"
                      onClick={() => markPaidMutation.mutate({ id: row.id, status: row.status === 'paid' ? 'projected' : 'paid' })}
                      disabled={markPaidMutation.isPending}
                      className="inline-flex items-center justify-center"
                      title={row.status === 'paid' ? t('loans.markUnpaid') : t('loans.markPaid')}
                    >
                      {row.status === 'paid' ? (
                        <CheckCircle2 size={16} className="text-emerald-500" />
                      ) : (
                        <Circle size={16} className="text-muted-foreground" />
                      )}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LoanFormDialog({
  open,
  onClose,
  loan,
  categories,
  onSave,
  loading,
}: {
  open: boolean
  onClose: () => void
  loan: LoanSummary | null
  categories: { id: string; name: string }[]
  onSave: (data: LoanFormInput) => void
  loading: boolean
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState<LoanFormInput>(emptyForm)

  useEffect(() => {
    if (loan) {
      const d = loan.details
      setForm({
        name: d.name,
        currency: d.currency,
        principal_amount: d.principal_amount,
        interest_rate: d.interest_rate * 100,
        rate_period: d.rate_period,
        amortization_system: d.amortization_system,
        term_months: d.term_months,
        start_date: d.start_date,
        insurance_monthly: d.insurance_monthly,
        admin_fee_monthly: d.admin_fee_monthly,
        payment_category_id: d.payment_category_id,
      })
    } else {
      setForm({ ...emptyForm, start_date: localDateString() })
    }
  }, [loan, open])

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{loan ? t('loans.edit') : t('loans.add')}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            onSave({
              ...form,
              interest_rate: form.interest_rate / 100,
              principal_amount: Number(form.principal_amount),
              term_months: Number(form.term_months),
            })
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-3">
            <div className="space-y-2">
              <Label>{t('loans.name')}</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('loans.principal')}</Label>
                <Input
                  type="number" step="0.01" min="0" required
                  value={form.principal_amount || ''}
                  onChange={(e) => setForm({ ...form, principal_amount: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('loans.termMonths')}</Label>
                <Input
                  type="number" min="1" required
                  value={form.term_months || ''}
                  onChange={(e) => setForm({ ...form, term_months: parseInt(e.target.value, 10) || 0 })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('loans.rate')}</Label>
                <Input
                  type="number" step="0.01" min="0" required placeholder="10.5"
                  value={form.interest_rate || ''}
                  onChange={(e) => setForm({ ...form, interest_rate: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('loans.ratePeriod')}</Label>
                <select
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-card text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  value={form.rate_period}
                  onChange={(e) => setForm({ ...form, rate_period: e.target.value as 'annual' | 'monthly' })}
                >
                  <option value="annual">{t('loans.rateAnnual')}</option>
                  <option value="monthly">{t('loans.rateMonthly')}</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('loans.system')}</Label>
                <select
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-card text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  value={form.amortization_system}
                  onChange={(e) => setForm({ ...form, amortization_system: e.target.value as 'sac' | 'price' })}
                >
                  <option value="sac">{t('loans.systemSac')}</option>
                  <option value="price">{t('loans.systemPrice')}</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>{t('loans.startDate')}</Label>
                <DatePickerInput
                  value={form.start_date}
                  onChange={(v) => setForm({ ...form, start_date: v })}
                  className="w-full justify-start"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('loans.insurance')}</Label>
                <Input
                  type="number" step="0.01" min="0" placeholder="0.00"
                  value={form.insurance_monthly ?? ''}
                  onChange={(e) => setForm({ ...form, insurance_monthly: e.target.value !== '' ? parseFloat(e.target.value) : null })}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('loans.adminFee')}</Label>
                <Input
                  type="number" step="0.01" min="0" placeholder="0.00"
                  value={form.admin_fee_monthly ?? ''}
                  onChange={(e) => setForm({ ...form, admin_fee_monthly: e.target.value !== '' ? parseFloat(e.target.value) : null })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t('loans.paymentCategory')}</Label>
              <select
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-card text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                value={form.payment_category_id ?? ''}
                onChange={(e) => setForm({ ...form, payment_category_id: e.target.value || null })}
              >
                <option value="">{t('loans.paymentCategoryNone')}</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">{t('loans.paymentCategoryHint')}</p>
            </div>
          </div>
          <DialogFooter className="mt-2 shrink-0 border-t pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? t('common.loading') : t('common.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
