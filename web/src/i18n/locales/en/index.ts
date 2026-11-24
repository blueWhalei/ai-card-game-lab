import report from './report'
import traceCitation from './traceCitation'
import scenarioRecords from './scenarioRecords'
import common from './common'
import guide from './guide'
import experiment from './experiment'
import game from './game'
import analyze from './analyze'
import settings from './settings'
import study from './study'
import promptDesign from './promptDesign'
import focus from './focus'
import paired from './paired'

import desktopClose from './desktopClose'
import operations from './operations'
import finance from './finance'
import billing from './billing'
export default {
  ...billing,
  ...finance,
  ...operations,
  ...traceCitation,
  ...scenarioRecords,
  ...report,
  ...desktopClose,
  ...paired,
  ...focus,
  ...promptDesign,
  ...study,
  ...common,
  ...guide,
  ...experiment,
  ...game,
  ...analyze,
  ...settings,
}
