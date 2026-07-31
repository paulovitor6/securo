import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { loans as loansApi } from '@/lib/api'
import { useDisplayLocale, useDateLocale } from '@/hooks/use-display-locale'
import { formatCurrency } from '@/lib/format'
import { localDateString } from '@/lib/date-utils'
import { usePrivacyMode } from '@/hooks/use-privacy-mode'
import { useWorkspace } from '@/contexts/workspace-context'
import { CheckCircle2, Circle } from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-card rounded-xl border border-border shadow-sm p-3">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className="text-base font-bold text-foreground tabular-nums">{value}</p>
    </div>
  )
}

export function LoanScheduleSection({ accountId, currency }: { accountId: string; currency: string }) {
  const { t } = useTranslation()
  const locale = useDisplayLocale()
  const dateLocale = useDateLocale()
  const { mask } = usePrivacyMode()
  const { canWrite } = useWorkspace()
  const queryClient = useQueryClient()

  const { data: summary } = useQuery({
    queryKey: ['loan', accountId],
    queryFn: () => loansApi.get(accountId),
  })
  const { data: installments } = useQuery({
    queryKey: ['loan-installments', accountId],
    queryFn: () => loansApi.installments(accountId),
  })

  const markPaidMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'paid' | 'projected' }) =>
      loansApi.markInstallment(accountId, id, {
        status,
        paid_date: status === 'paid' ? localDateString() : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loan', accountId] })
      queryClient.invalidateQueries({ queryKey: ['loan-installments', accountId] })
    },
  })

  if (!summary) return null

  const formatDate = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(dateLocale)
  const chartData = (installments ?? []).map((i) => ({ date: i.due_date, balance: i.outstanding_balance_after }))

  return (
    <div className="space-y-4 mb-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard
          label={t('accounts.loanOutstandingBalance')}
          value={mask(formatCurrency(summary.outstanding_balance, currency, locale))}
        />
        <SummaryCard
          label={t('accounts.loanInstallmentsProgress')}
          value={`${summary.installments_paid}/${summary.installments_total}`}
        />
        <SummaryCard
          label={t('accounts.loanNextDueDate')}
          value={summary.next_installment ? formatDate(summary.next_installment.due_date) : '—'}
        />
        <SummaryCard
          label={t('accounts.loanNextAmount')}
          value={summary.next_installment ? mask(formatCurrency(summary.next_installment.total_amount, currency, locale)) : '—'}
        />
      </div>

      {chartData.length > 0 && (
        <div className="bg-card rounded-xl border border-border shadow-sm p-4">
          <p className="text-sm font-semibold text-foreground mb-3">{t('accounts.loanBalanceChart')}</p>
          <ResponsiveContainer width="100%" height={200}>
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

      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm font-semibold text-foreground">{t('accounts.loanSchedule')}</p>
        </div>
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border">
                <th className="text-left px-3 py-2 font-medium text-muted-foreground">#</th>
                <th className="text-left px-3 py-2 font-medium text-muted-foreground">{t('accounts.loanDueDate')}</th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">{t('accounts.loanAmortization')}</th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">{t('accounts.loanInterest')}</th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground">{t('accounts.loanTotal')}</th>
                <th className="text-right px-3 py-2 font-medium text-muted-foreground hidden sm:table-cell">{t('accounts.loanOutstandingAfter')}</th>
                {canWrite && <th className="text-center px-3 py-2 font-medium text-muted-foreground">{t('accounts.loanStatus')}</th>}
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
                        title={row.status === 'paid' ? t('accounts.loanMarkUnpaid') : t('accounts.loanMarkPaid')}
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
    </div>
  )
}
