import { check, sleep } from 'k6';
import { createOpeningHour } from './mocks.js';
import { getRandomArbitrary } from './utils.js';

const commands = (session) => {
  const viewResource = (origId, resourceId) => {
    session.post(`/resource/${origId}/permission_check/`);
    session.request('OPTIONS', '/date_period/');

    const response = session.get(
      `/date_period/?resource=${resourceId}&end_date_gte=-1d&format=json`
    );

    check(response, {
      'GET date periods status is 200': (r) => r.status === 200,
    });

    check(session.get(`/resource/${origId}/?format=json`), {
      'GET resource status is status 200': (r) => r.status === 200,
    });

    return response.json();
  };

  const viewDatePeriod = (resourceId, datePeriodId) => {
    session.post(`/resource/${resourceId}/permission_check/`);

    check(session.get(`/resource/${resourceId}/?format=json`), {
      'GET resource status is status 200': (r) => r.status === 200,
    });

    check(session.get(`/date_period/${datePeriodId}/?format=json`), {
      'GET date period status is 200': (r) => r.status === 200,
    });

    session.request('OPTIONS', '/date_period/');
  };

  const addNewDatePeriod = (resourceId) => {
    session.post(`/resource/${resourceId}/permission_check/`);
    session.request('OPTIONS', '/date_period/');

    check(session.get(`/resource/${resourceId}/?format=json`), {
      'GET resource status is status 200': (r) => r.status === 200,
    });

    sleep(getRandomArbitrary(10, 20));

    const response = session.post(
      '/date_period/',
      JSON.stringify(createOpeningHour(resourceId)),
      {
        headers: { 'Content-Type': 'application/json' },
      }
    );

    check(response, {
      'POST date period status is status 201': (r) => r.status === 201,
    });
  };

  return {
    addNewDatePeriod,
    viewDatePeriod,
    viewResource,
  };
};

export default commands;
