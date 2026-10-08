// Runs independent tasks on every core of the computer: reading the frames and
// matching each pair of neighbours do not depend on one another.

#pragma once

#include <algorithm>
#include <atomic>
#include <exception>
#include <mutex>
#include <thread>
#include <vector>

namespace merge
{

// Calls task(i) for every i from 0 to count - 1, on as many threads as the
// computer has cores, at most count, and returns once all are done. If a task
// throws, the others still finish, and the first exception is thrown again.
template <typename Task>
void parallelFor(int count, Task task)
{
  const int threads = std::max(1, std::min(count, static_cast<int>(std::thread::hardware_concurrency())));
  std::atomic<int> next{ 0 };
  std::exception_ptr error;
  std::mutex error_mutex;
  auto work = [&]() {
    for (int i = next++; i < count; i = next++)
    {
      try
      {
        task(i);
      }
      catch (...)
      {
        const std::lock_guard<std::mutex> lock(error_mutex);
        if (!error)
        {
          error = std::current_exception();
        }
      }
    }
  };
  std::vector<std::thread> workers;
  for (int t = 1; t < threads; ++t)
  {
    workers.emplace_back(work);
  }
  work();
  for (std::thread& worker : workers)
  {
    worker.join();
  }
  if (error)
  {
    std::rethrow_exception(error);
  }
}

}  // namespace merge
