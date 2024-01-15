/* eslint-disable import/prefer-default-export */
export const createOpeningHour = (resource) => ({
  resource,
  name: { fi: `load-test ${new Date().toISOString()}`, sv: '', en: '' },
  description: { fi: '', sv: '', en: '' },
  start_date: '2022-01-01',
  end_date: '2022-12-31',
  resource_state: 'undefined',
  override: false,
  time_span_groups: [
    {
      rules: [],
      time_spans: [
        {
          description: { fi: null, sv: null, en: null },
          end_time: '16:00:00',
          start_time: '08:00:00',
          resource_state: 'open',
          full_day: false,
          weekdays: [1, 2, 3, 4, 5],
        },
        {
          description: { fi: null, sv: null, en: null },
          end_time: '18:00:00',
          start_time: '10:00:00',
          resource_state: 'open',
          full_day: false,
          weekdays: [6],
        },
      ],
    },
  ],
});
