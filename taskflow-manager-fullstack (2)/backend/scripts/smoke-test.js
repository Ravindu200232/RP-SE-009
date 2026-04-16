const { serviceUrls } = require('../shared/config');

const expect = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const requestJson = async (path, options = {}) => {
  const response = await fetch(`${serviceUrls.gateway}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.success) {
    throw new Error(payload?.error || `Request failed for ${path}`);
  }

  return payload;
};

const requestHealth = async (url, label) => {
  const response = await fetch(url);
  const payload = await response.json().catch(() => null);
  expect(response.ok, `${label} health endpoint returned ${response.status}`);
  expect(payload?.status === 'ok', `${label} health endpoint did not return ok status`);
  return payload;
};

const main = async () => {
  console.log('Checking service health...');
  const gatewayHealth = await requestHealth(`${serviceUrls.gateway}/health`, 'Gateway');
  const tasksHealth = await requestHealth(`${serviceUrls.tasks}/health`, 'Tasks service');
  const boardHealth = await requestHealth(`${serviceUrls.board}/health`, 'Board service');

  console.log(`Gateway healthy on ${serviceUrls.gateway}`);
  console.log(`Tasks service storage mode: ${tasksHealth.storage?.mode || 'unknown'}`);
  console.log(`Board service healthy on ${serviceUrls.board}`);

  console.log('Seeding backend sample data...');
  const seeded = await requestJson('/api/tasks/seed', {
    method: 'POST',
    body: JSON.stringify({ replace: true }),
  });
  expect(Array.isArray(seeded.data) && seeded.data.length >= 3, 'Sample data seeding failed');

  console.log('Creating a new task through the gateway...');
  const created = await requestJson('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({
      title: 'Smoke test task',
      description: 'Created by backend/scripts/smoke-test.js',
      priority: 'high',
      status: 'todo',
    }),
  });
  expect(created.data?._id, 'Created task is missing an id');

  console.log('Updating the task through the board service...');
  const movedBoard = await requestJson('/api/board/move-task', {
    method: 'PATCH',
    body: JSON.stringify({
      taskId: created.data._id,
      toColumn: 'in-progress',
      newPosition: 0,
    }),
  });
  const boardTaskIds = movedBoard.data.columns.flatMap((column) => column.tasks.map((task) => task._id));
  expect(boardTaskIds.includes(created.data._id), 'Moved task was not returned by the board service');

  console.log('Verifying task persistence...');
  const taskList = await requestJson('/api/tasks');
  expect(
    taskList.data.some((task) => task._id === created.data._id && task.status === 'in-progress'),
    'Updated task state was not persisted'
  );

  console.log('Deleting the smoke test task...');
  await requestJson(`/api/tasks/${created.data._id}`, {
    method: 'DELETE',
  });

  const finalTasks = await requestJson('/api/tasks');
  expect(
    !finalTasks.data.some((task) => task._id === created.data._id),
    'Smoke test task still exists after delete'
  );

  console.log('Smoke test passed.');
  console.log(`Gateway timestamp: ${gatewayHealth.timestamp}`);
  console.log(`Tasks storage mode: ${tasksHealth.storage?.mode || 'unknown'}`);
  console.log(`Board timestamp: ${boardHealth.timestamp}`);
};

main().catch((error) => {
  console.error(`Smoke test failed: ${error.message}`);
  process.exit(1);
});
