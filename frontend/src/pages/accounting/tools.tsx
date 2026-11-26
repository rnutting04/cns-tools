import type { ReactElement } from 'react'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import GavelIcon from '@mui/icons-material/Gavel'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import EventIcon from '@mui/icons-material/Event'
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong'
import TableChartIcon from '@mui/icons-material/TableChart'

/** Tools are grouped by the file they read, so one month's file finds all its checks. */
export type ToolGroup = 'packets' | 'balance_sheet' | 'income_expense' | 'reserve_schedule'

export const TOOL_GROUPS: { id: ToolGroup; title: string; description: string }[] = [
  {
    id: 'balance_sheet',
    title: 'Balance sheet checks',
    description: 'Run on the combined balance sheet file for all associations.',
  },
  {
    id: 'income_expense',
    title: 'Income & expense checks',
    description: 'Run on the combined income & expense file.',
  },
  {
    id: 'packets',
    title: 'Financial packets',
    description: 'One association’s monthly packet at a time.',
  },
  {
    id: 'reserve_schedule',
    title: 'Reserve schedule',
    description: 'The MASS Reserve Schedule workbook (Excel), separate from the PDF checks.',
  },
]

export interface AccountingTool {
  /** route segment under /accounting */
  path: string
  title: string
  description: string
  /** what to upload */
  input: string
  group: ToolGroup
  icon: ReactElement
}

export const ACCOUNTING_TOOLS: AccountingTool[] = [
  {
    path: 'fdic',
    title: 'FDIC exposure',
    description: 'Adds up balances at each bank from the balance sheet and flags $250,000 or more.',
    input: 'Balance sheet PDFs',
    group: 'balance_sheet',
    icon: <AccountBalanceIcon />,
  },
  {
    path: 'cd-maturity',
    title: 'CD maturity',
    description:
      'Lists every CD by when it matures and flags those matured, due within 30, 60 or 90 days, or missing a date.',
    input: 'Balance sheet PDFs',
    group: 'balance_sheet',
    icon: <EventIcon />,
  },
  {
    path: 'ar-prepaid',
    title: 'AR & prepaid',
    description:
      'Ties every association’s Accounts Receivable (1100) and Prepaid Assessments (2100) to the AR and prepaid reports.',
    input: 'Balance sheet, AR and prepaid PDFs',
    group: 'balance_sheet',
    icon: <ReceiptLongIcon />,
  },
  {
    path: 'audit-threshold',
    title: 'Audit threshold',
    description:
      'Totals operating and reserve revenues and shows whether a compilation, review or audit is needed.',
    input: 'Income & expense PDFs',
    group: 'income_expense',
    icon: <GavelIcon />,
  },
  {
    path: 'review',
    title: 'Financial review',
    description:
      'Ties each balance sheet to its bank reconciliations and supporting reports. Review a whole month of packets in one session.',
    input: 'Financial packet PDFs',
    group: 'packets',
    icon: <FactCheckIcon />,
  },
  {
    path: 'reserve-schedule',
    title: 'Reserve schedule',
    description:
      'Checks every association tab of the MASS Reserve Schedule for negative component balances.',
    input: 'Excel workbook (.xlsx)',
    group: 'reserve_schedule',
    icon: <TableChartIcon />,
  },
]
