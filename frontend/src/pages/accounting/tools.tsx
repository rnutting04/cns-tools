import type { ReactElement } from 'react'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import GavelIcon from '@mui/icons-material/Gavel'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import TableChartIcon from '@mui/icons-material/TableChart'

export interface AccountingTool {
  /** route segment under /accounting */
  path: string
  title: string
  description: string
  /** what to upload */
  input: string
  icon: ReactElement
}

export const ACCOUNTING_TOOLS: AccountingTool[] = [
  {
    path: 'review',
    title: 'Financial review',
    description:
      'Ties each balance sheet to its bank reconciliations and supporting reports. Review a whole month of packets in one session.',
    input: 'Financial packet PDFs',
    icon: <FactCheckIcon />,
  },
  {
    path: 'audit-threshold',
    title: 'Audit threshold',
    description:
      'Totals operating and reserve revenues and shows whether a compilation, review or audit is needed.',
    input: 'Income & expense PDFs',
    icon: <GavelIcon />,
  },
  {
    path: 'fdic',
    title: 'FDIC exposure',
    description: 'Adds up balances at each bank from the balance sheet and flags $250,000 or more.',
    input: 'Balance sheet PDFs',
    icon: <AccountBalanceIcon />,
  },
  {
    path: 'reserve-schedule',
    title: 'Reserve schedule',
    description:
      'Checks every association tab of the MASS Reserve Schedule for negative component balances.',
    input: 'Excel workbook (.xlsx)',
    icon: <TableChartIcon />,
  },
]
