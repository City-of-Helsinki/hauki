/* eslint-disable import/prefer-default-export */
export const getRandomArbitrary = (min, max) => {
  return Math.random() * (max - min) + min;
};

export const formatDate = (d) => d.toISOString().split('T')[0];
