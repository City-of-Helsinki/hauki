/* eslint-disable */
import { check, group, sleep } from 'k6';
import { Httpx } from 'https://jslib.k6.io/httpx/0.0.1/index.js';
import { createOpeningHour } from './helpers/mocks.js';
import commands from './helpers/commands.js';
import { formatDate, getRandomArbitrary } from './helpers/utils.js';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.1/index.js';

const {
  AUTH_PARAMS: authParams,
  API_URL: apiUrl,
  HAUKI_RESOURCE: tprekResourceId,
} = __ENV;

const IDLE_TIME = 10;

const session = new Httpx();
session.setBaseUrl(`${apiUrl}`);
// session.addHeader('Authorization', `haukisigned ${authParams}`);

const { addNewDatePeriod, viewResource } = commands(session);

export const options = {
  thresholds: {
    http_req_duration: ['p(90) < 2000'],
  },
  scenarios: {
    // add requires authorization
    // addOpeningHours: {
    //   executor: 'constant-vus',
    //   exec: 'addOpeningHours',
    //   vus: 5,
    //   duration: '1m',
    // },
    requestOpeningHours: {
      executor: 'constant-vus',
      exec: 'requestOpeningHours',
      vus: 50,
      duration: '1m',
    },
  },
  teardownTimeout: '5m',
};

export function setup() {
  const { id } = session
    .get(`/resource/${tprekResourceId}/?format=json`)
    .json();

  session.post('/date_period/', JSON.stringify(createOpeningHour(id)), {
    headers: { 'Content-Type': 'application/json' },
  });

  const resources = session.get('/resource/').json();

  return { resourceId: id, resources };
}

export function addOpeningHours({ resourceId }) {
  viewResource(tprekResourceId, resourceId);
  sleep(getRandomArbitrary(10, IDLE_TIME));
  addNewDatePeriod(resourceId);
  viewResource(tprekResourceId, resourceId);
}

export function requestOpeningHours({ resources }) {
  const random = Math.floor(Math.random() * resources.results.length);
  const resourceId = resources.results[random].id;

  group('Get opening hours', () => {
    sleep(getRandomArbitrary(1, 5));

    const startDate = new Date();
    const endDate = new Date();
    endDate.setDate(startDate.getDate() + 365);

    const url = `/resource/${resourceId}/opening_hours/?start_date=${formatDate(
      startDate
    )}&end_date=${formatDate(endDate)}`;

    const start = new Date().toISOString();
    const result = session.get(url);

    if (result.status !== 200) {
      console.log(
        JSON.stringify(
          {
            url: `${apiUrl}/${url}`,
            status: result.status,
            start,
            end: new Date().toISOString(),
            body: JSON.stringify(result.body),
          },
          null,
          2
        )
      );
    }

    check(result, {
      'Fetching opening hours returns 200': (r) => r.status === 200,
    });
  });
}

export function teardown({ resourceId }) {
  const response = session
    .get(`/date_period/?resource=${resourceId}&end_date_gte=-1d&format=json`)
    .json();

  const toBeDeleted = response.filter((datePeriod) =>
    datePeriod.name.fi.includes('load-test')
  );

  toBeDeleted.forEach((datePeriod) => {
    session.delete(`/date_period/${datePeriod.id}/`);
  });

  console.log(`Deleted date periods: ${toBeDeleted.length}`);
}

export function handleSummary(data) {
  return {
    'summary.html': htmlReport(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
