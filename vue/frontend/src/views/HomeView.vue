<!-- frontend/src/views/HomeView.vue -->
<template>
  <div class="home">
    <h1>Welcome, {{ currentUser?.username }}</h1>
    <p v-if="currentUser">
      Payroll: {{ currentUser.payroll }} &nbsp;|&nbsp; Dept: {{ currentUser.deptcode }}
    </p>
    <p class="text-primary font-bold">Tailwind Test</p>
    <button class="btn btn-primary">DaisyUI Test</button>

    <div class="mt-4">
      <h2 class="font-bold">Access Codes</h2>
      <p v-if="!accessCodes.length" class="text-gray-400">No access codes.</p>
      <ul v-else class="mt-2 space-y-1 text-sm">
        <li v-for="ac in accessCodes" :key="ac.msc14036 + ac.rto0006" class="font-mono">
          {{ ac.rto0006 }} | {{ ac.msc14036 }} | {{ ac.rto0011_01 }} | {{ ac.rto0011_02 }} | {{ ac.rto0011_03 }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { useAuth } from '../composables/useAuth.js'
import { useRbac } from '../composables/useRbac.js'

const { currentUser } = useAuth()
const { accessCodes } = useRbac()
</script>
