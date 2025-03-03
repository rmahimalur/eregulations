<script setup>
import { computed, reactive, watch } from "vue";

import { useRouter, useRoute } from "vue-router/composables";

import _debounce from "lodash/debounce";
import _isArray from "lodash/isArray";

import { getSubjectName } from "utilities/filters";

import SimpleSpinner from "eregsComponentLib/src/components/SimpleSpinner.vue";

const props = defineProps({
    policyDocSubjects: {
        type: Object,
        default: () => ({ results: [], loading: true }),
    },
});

const $router = useRouter();
const $route = useRoute();

const state = reactive({
    filter: "",
    subjects: [],
});

watch(
    () => props.policyDocSubjects.loading,
    (loading) => {
        if (loading) {
            state.subjects = [];
            return;
        }

        state.subjects = props.policyDocSubjects.results;
    }
);

const getFilteredSubjects = (filter) => {
    if (!filter || filter.length < 1) {
        state.subjects = props.policyDocSubjects.results;
        return;
    }

    state.subjects = props.policyDocSubjects.results.reduce((acc, subject) => {
        const shortNameMatch = subject.short_name
            ? subject.short_name.toLowerCase().includes(filter.toLowerCase())
            : false;
        const abbreviationMatch = subject.abbreviation
            ? subject.abbreviation.toLowerCase().includes(filter.toLowerCase())
            : false;
        const fullNameMatch = subject.full_name
            ? subject.full_name.toLowerCase().includes(filter.toLowerCase())
            : false;

        if (shortNameMatch || abbreviationMatch || fullNameMatch) {
            let displayName;

            if (shortNameMatch) {
                displayName = subject.short_name;
            } else if (abbreviationMatch) {
                displayName = subject.abbreviation;
            } else if (fullNameMatch) {
                displayName = subject.full_name;
            }

            displayName =
                "<span class='match__container'>" +
                displayName.replace(
                    new RegExp(filter, "gi"),
                    (match) => `<span class="match">${match}</span>`
                ) +
                "</span>";

            const newSubject = {
                ...subject,
                displayName,
            };

            return [...acc, newSubject];
        }

        return acc;
    }, []);
};

const debouncedFilter = _debounce(getFilteredSubjects, 100);

watch(() => state.filter, debouncedFilter);

const subjectClick = (event) => {
    const subjects = $route?.query?.subjects ?? [];
    const subjectsArray = _isArray(subjects) ? subjects : [subjects];
    const subjectToAdd = event.currentTarget.dataset.id;

    if (subjectsArray.includes(subjectToAdd)) return;

    $router.push({
        name: "policy-repository",
        query: {
            ...$route.query,
            subjects: [subjectToAdd],
        },
    });
};

const subjectClasses = (subjectId) => ({
    "sidebar-li__button": true,
    "sidebar-li__button--selected": $route.query.subjects?.includes(
        subjectId.toString()
    ),
});

const filterResetClasses = computed(() => ({
    "subjects__filter-reset": true,
    "subjects__filter-reset--hidden": !state.filter,
}));

const filterResetClick = () => {
    state.filter = "";
};
</script>

<template>
    <div class="subjects__select-container">
        <h3>By Subject</h3>
        <div class="subjects__list-container">
            <template v-if="props.policyDocSubjects.loading">
                <div class="subjects__loading">
                    <SimpleSpinner />
                </div>
            </template>
            <template v-else>
                <form @submit.prevent>
                    <input
                        id="subjectReduce"
                        v-model="state.filter"
                        aria-label="Filter the subject list"
                        placeholder="Filter the subject list"
                        type="text"
                    />
                    <button
                        aria-label="Clear subject list filter"
                        data-testid="clear-subject-filter"
                        type="reset"
                        :class="filterResetClasses"
                        class="mdi mdi-close"
                        @click="filterResetClick"
                    ></button>
                </form>
                <ul tabindex="-1" class="subjects__list">
                    <li
                        v-for="subject in state.subjects"
                        :key="subject.id"
                        class="subjects__li sidebar__li"
                    >
                        <button
                            :class="subjectClasses(subject.id)"
                            :data-name="getSubjectName(subject)"
                            :data-id="subject.id"
                            :data-testid="`add-subject-${subject.id}`"
                            :title="subject.full_name"
                            @click="subjectClick"
                            v-html="
                                subject.displayName || getSubjectName(subject)
                            "
                        ></button>
                    </li>
                </ul>
            </template>
        </div>
    </div>
</template>
